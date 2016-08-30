#!/usr/bin/env bash

echo "Copying your local env.sh settings to heroku"
echo "You should have run . env.sh before running this script"
echo ""
echo "ALSO NOTE: OAuth CLIENT_ID and CLIENT_SECRET may need to be different for heroku"

heroku config:set  GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID}   
heroku config:set  GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}
heroku config:set  APP_SECRET_KEY=${APP_SECRET_KEY}
heroku config:set  GITHUB_ORG=${GITHUB_ORG}

heroku config:set  MONGO_HOST=${MONGO_HOST}    
heroku config:set  MONGO_PORT=${MONGO_PORT}
heroku config:set  MONGO_DBNAME=${MONGO_DBNAME}
heroku config:set  MONGO_USERNAME=${MONGO_USERNAME}
heroku config:set  MONGO_PASSWORD=${MONGO_PASSWORD}

