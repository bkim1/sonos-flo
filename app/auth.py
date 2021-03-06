from urllib import parse
import os
import base64
import time

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)

import requests


bp = Blueprint('auth', __name__, url_prefix='/auth')


SONOS_AUTH_URL = 'https://api.sonos.com/login/v3/oauth'
LOGIN_REDIRECT_URI = parse.quote('https://sonos-flow.now.sh/auth/login-redirect', safe='')
LOGIN_LOCAL_REDIRECT_URI = parse.quote('http://localhost:5000/auth/login-redirect/1', safe='')
FLOW_SETUP_URI = 'https://sonos-flow.now.sh/flow'
FLOW_SETUP_LOCAL_URI = 'http://localhost:5000/flow'


@bp.route('/login', defaults={'local': 0})
@bp.route('/login/<int:local>', methods=['GET'])
def authenticate(local):
    """ Constructs the proper uri and redirects the client to the Sonos Login

        Args:
            local: int specifying whether the redirect should go to localhost
                   or the deployed instance
    """
    client_key = parse.quote(os.getenv("CLIENT_KEY"), safe='')
    state = os.getenv("STATE")
    redirect_uri = LOGIN_LOCAL_REDIRECT_URI if local else LOGIN_REDIRECT_URI

    auth_url = f'{SONOS_AUTH_URL}' \
               f'?client_id={client_key}' \
               f'&response_type=code' \
               f'&state={state}' \
               f'&scope=playback-control-all' \
               f'&redirect_uri={redirect_uri}'
    return redirect(auth_url)


@bp.route('/login-redirect', defaults={'local': 0}, methods=['GET'])
@bp.route('/login-redirect/<int:local>', methods=['GET'])
def handle_login_redirect(local):
    """ Handles the redirect after authorizing Sonos Flow and gets the access
        token for API calls to Sonos. Sets the access token to an environment
        variable for use later.

        Args:
            local: int specifying whether the redirect should go to localhost
                   or the deployed instance 
    """
    if os.getenv('STATE') != request.args['state']:
        return 'Invalid Redirect... Wrong State'

    auth_code = request.args['code']

    client_key, secret_key = os.getenv('CLIENT_KEY'), os.getenv('CLIENT_SECRET')

    # Base64 Encode 'ClientKey:SecretKey'
    key_pair = f'{client_key}:{secret_key}'
    encoded_keys = base64.b64encode(bytes(key_pair, 'utf-8'))
    encoded_keys_str = encoded_keys.decode('utf-8')

    redirect_uri = LOGIN_LOCAL_REDIRECT_URI if local else LOGIN_REDIRECT_URI

    # Set Headers & Data for request
    auth_url = f'{SONOS_AUTH_URL}/access'
    headers = { 'Authorization': 'Basic %s' % encoded_keys_str, }
    payload = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': redirect_uri
    }

    # Make POST request for Access Token
    resp = requests.post(auth_url, data=payload, headers=headers)
    json_data = resp.json()

    # Set tokens in environment variables for later access
    os.environ['AccessToken'] = json_data['access_token']
    os.environ['RefreshToken'] = json_data['refresh_token']
    os.environ['TokenCreated'] = str(time.time())
    os.environ['ExpiresIn'] = str(json_data['expires_in'])

    flow_setup_redirect = FLOW_SETUP_LOCAL_URI if local else FLOW_SETUP_URI
    
    return redirect(flow_setup_redirect)
