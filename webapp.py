from flask import Flask, redirect, url_for, session, request, jsonify
from flask_oauthlib.client import OAuth
from flask import render_template, flash, Markup

from flask.ext.pymongo import PyMongo
from flask.ext.pymongo import ObjectId


from github import Github

import pprint
import os
import sys
import traceback

class GithubOAuthVarsNotDefined(Exception):
    '''raise this if the necessary env variables are not defined '''

env_vars_needed = ['GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET',
                   'APP_SECRET_KEY', 'GITHUB_ORG', 
                   'MONGO_HOST', 'MONGO_PORT', 'MONGO_DBNAME', 
                   'MONGO_USERNAME', 'MONGO_PASSWORD']

for e in env_vars_needed: 
    if os.getenv(e) == None:
        raise GithubOAuthVarsNotDefined(
            "Please define environment variables: \r\n" + 
            pprint.pformat(env_vars_needed) + """
For local operation, define in env.sh, then at command line, run:
  . env.sh
For Heroku, define variables via Settings=>Reveal Config Vars

""" )


app = Flask(__name__)

app.secret_key = os.environ['APP_SECRET_KEY']
oauth = OAuth(app)

app.config['MONGO_HOST'] = os.environ['MONGO_HOST']
app.config['MONGO_PORT'] = int(os.environ['MONGO_PORT'])
app.config['MONGO_DBNAME'] = os.environ['MONGO_DBNAME']
app.config['MONGO_USERNAME'] = os.environ['MONGO_USERNAME']
app.config['MONGO_PASSWORD'] = os.environ['MONGO_PASSWORD']
mongo = PyMongo(app)

# This code originally from https://github.com/lepture/flask-oauthlib/blob/master/example/github.py
# Edited by P. Conrad for SPIS 2016 to add getting Client Id and Secret from
# environment variables, so that this will work on Heroku.


github = oauth.remote_app(
    'github',
    consumer_key=os.environ['GITHUB_CLIENT_ID'],
    consumer_secret=os.environ['GITHUB_CLIENT_SECRET'],
    request_token_params={'scope': 'read:org'},
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize'
)

@app.context_processor
def inject_logged_in():
    return dict(logged_in=(is_logged_in()))

@app.context_processor
def inject_github_org():
    return dict(github_org=os.getenv('GITHUB_ORG'))

def is_logged_in():
    return 'github_token' in session

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    return github.authorize(callback=url_for('authorized', _external=True))

@app.route('/logout')
def logout():
    session.clear()
    flash('You were logged out')
    return redirect(url_for('home'))

@app.route('/login/authorized')
def authorized():
    resp = github.authorized_response()

    if resp is None:
        session.clear()
        login_error_message = 'Access denied: reason=%s error=%s full=%s' % (
            request.args['error'],
            request.args['error_description'],
            pprint.pformat(request.args)
        )        
        flash(login_error_message, 'error')
        return redirect(url_for('home'))    

    try:
        session['github_token'] = (resp['access_token'], '')
        session['user_data']=github.get('user').data
        github_userid = session['user_data']['login']
        org_name = os.getenv('GITHUB_ORG')
    except Exception as e:
        session.clear()
        message = 'Unable to login: ' + str(type(e)) + str(e)
        flash(message,'error')
        return redirect(url_for('home'))
    
    try:
        g = Github(resp['access_token'])
        org = g.get_organization(org_name)
        named_user = g.get_user(github_userid)
        isMember = org.has_in_members(named_user)
    except Exception as e:
        message = 'Unable to connect to Github with accessToken: ' + resp['access_token'] + " exception info: " + str(type(e)) + str(e)
        session.clear()
        flash(message,'error')
        return redirect(url_for('home'))
    
    if not isMember:
        session.clear() # Must clear session before adding flash message
        message = 'Unable to login: ' + github_userid + ' is not a member of ' + org_name + \
          '</p><p><a href="https://github.com/logout" target="_blank">Logout of github as user:  ' + github_userid + \
          '</a></p>' 
        flash(Markup(message),'error')

    else:
        flash('You were successfully logged in')

    return redirect(url_for('home'))    

@app.route('/listAll')
def listAll():
    if not is_logged_in():
        flash("You must be logged in to do that",'error')
        return redirect(url_for('home')) 
    login = session['user_data']['login']   
    userinputs = [x for x in mongo.db.mycollection.find()]
    return render_template('list.html',userinputs = userinputs,login=login)

@app.route('/listMine')
def listMine():
    if not is_logged_in():
        flash("You must be logged in to do that",'error')
        return redirect(url_for('home'))    
    login = session['user_data']['login']
    userinputs = [x for x in mongo.db.mycollection.find({'login':login})]
    return render_template('list.html',userinputs = userinputs,login=login)


@app.route('/add')
def add():
    if not is_logged_in():
        flash("You must be logged in to do that",'error')
        return redirect(url_for('home'))    
    return render_template('add.html')

@app.route('/delete/<oid>',methods=['POST'])
def delete(oid):
    if not is_logged_in():
        flash("You must be logged in to do that",'error')
        return redirect(url_for('home'))    
    login = session['user_data']['login']    
    result = mongo.db.mycollection.find_one({'_id': ObjectId(oid)})
    if not 'login' in result:
        flash("Error deleting record with oid " + repr(oid) + "; could not determine user for record",
              "error")
        return redirect(url_for('listAll'))
    elif result['login'] != login:              
        flash("Cannot delete record for oid " + 
              repr(oid) + " belonging to user " + result['login'],'error')
        return redirect(url_for('listAll'))
                  
    result = mongo.db.mycollection.delete_one({'_id': ObjectId(oid),'login':login})
    if result.deleted_count == 0:
        flash("Error: Record with oid " + repr(oid) + " was not deleted",'error')
    elif result.deleted_count == 1:
        flash("Record with oid " + repr(oid) + " deleted")
    else:
        flash("Error: Unexpected result.deleted_count=" + \
                  str(result.deleted_count))

    return redirect(url_for('listAll'))


@app.route('/write',methods=['POST'])
def write():
    if not is_logged_in():
        flash("You must be logged in to do that",'error')
        return redirect(url_for('home'))    
    title = request.form.get("title") # match "id", "name" in form
    content = request.form.get("content") # match "id", "name" in form
    login = session['user_data']['login']    
    result = mongo.db.mycollection.insert_one(
            {
                "title"   : title, 
                "content" : content,
                "login"   : login
            }
        )
    flash("Saved to database with oid=" + str(result.inserted_id))
    return redirect(url_for('listAll'))

@github.tokengetter
def get_github_oauth_token():
    return session.get('github_token')


@app.route('/page1')
def render_page1():
    return render_template('page1.html')

@app.route('/page2')
def render_page2():
    return render_template('page2.html')

@app.route('/page3')
def render_page3():
    return render_template('page3.html')


@app.route('/page4')
def render_page4():
    return render_template('page4.html')

@app.route('/page5')
def render_page5():
    return render_template('page5.html')

if __name__=="__main__":
    app.run(debug=True, port=5000)
