import config
from sqlalchemy import create_engine, text
from app import create_app
import pytest
import json
import bcrypt

database = create_engine(config.test_config['DB_URL'], encoding='utf-8', max_overflow=0)


@pytest.fixture
def api():
    app = create_app(config.test_config)
    app.config['TEST'] = True
    api = app.test_client()

    return api

# test 실행 전 
def setup_function():
    # create test user
    hashed_password = bcrypt.hashpw(
        b'1234',
        bcrypt.gensalt()
    )
    new_users = [
        {
            'id'              : 1,
            'name'            : 'first',
            'email'           : 'test@test.com',
            'profile'         : 'first profile',
            'hashed_password' : hashed_password
        }, {
            'id'              : 2,
            'name'            : 'user',
            'email'           : 'user@test.com',
            'profile'         : 'second profile',
            'hashed_password' : hashed_password
        }
    ]
    database.execute(text("""
        INSERT INTO users (
            id,
            name,
            email,
            profile,
            hashed_password
        ) VALUES (
            :id,
            :name,
            :email,
            :profile,
            :hashed_password
        )
    """), new_users)

    # user2에 대한 tweet 미리 생성
    database.execute(text("""
                        INSERT INTO tweets (
                            user_id,
                            tweet
                        ) VALUES (
                            2,
                            "user2 test tweet"
                        )"""
                    ))

# test 실행 후 
def teardown_function():
    database.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    database.execute(text("TRUNCATE users"))
    database.execute(text("TRUNCATE tweets"))
    database.execute(text("TRUNCATE users_follow_list"))
    database.execute(text("SET FOREIGN_KEY_CHECKS=1"))

def test_ping(api):
    resp = api.get('/ping')
    assert b'pong' in resp.data


def test_login(api):
    resp = api.post(
        '/login',
        data = json.dumps({'email' : 'test@test.com', 'password' : '1234'}),
        content_type = 'application/json'
    )
    assert b"access_token" in resp.data 

def test_tweet(api):
    # 로그인
    resp = api.post(
        '/login',
        data = json.dumps({'email' : 'test@test.com', 'password' : '1234'}),
        content_type = 'application/json'
    )
    resp_json    = json.loads(resp.data.decode('utf-8'))
    access_token = resp_json['access_token']

    # tweet
    resp = api.post(
        '/tweet', 
        data         = json.dumps({'tweet' : "user1 test tweet"}),
        content_type = 'application/json',
        headers      = {'Authorization' : access_token}
    )
    assert resp.status_code == 200

    # tweet 조회
    resp   = api.get(f'/timeline/1')
    tweets = json.loads(resp.data.decode('utf-8'))

    assert resp.status_code == 200
    assert tweets           == { 
        'user_id'  : 1, 
        'timeline' : [
            {
                'user_id' : 1,
                'tweet'   : "user1 test tweet"
            }
        ]
    }

def test_unauthorized(api):
    # access token이 없으면 401 응답 리턴 확인
    resp = api.post(
        '/tweet',
        data = json.dumps({'tweet' : 'test tweet'}),
        content_type = 'application/json'
    )
    assert resp.status_code == 401

    resp = api.post(
        '/follow',
        data = json.dumps({'follow' : 2}),
        content_type = 'application/json'
    )
    assert resp.status_code == 401

    resp = api.post(
        '/unfollow',
        data = json.dumps({'unfollow' : 2}),
        content_type = 'application/json'
    )
    assert resp.status_code == 401

def test_follow(api):
    # login
    resp = api.post(
        '/login',
        data = json.dumps({'email':'test@test.com', 'password':'1234'}),
        content_type = 'application/json'
    )
    resp_json = json.loads(resp.data.decode('utf-8'))
    access_token = resp_json['access_token']

    # user1의 tweet리스트가 비어있는지 확인
    resp = api.get(f'/timeline/1')
    tweets = json.loads(resp.data.decode('utf-8'))

    assert resp.status_code == 200
    assert tweets == {
        'user_id' : 1,
        'timeline' : []
    }

    # user1(test)가 user2(user) follow
    resp = api.post(
        '/follow',
        data = json.dumps({'id':1, 'follow':2}),
        content_type = 'application/json',
        headers = {'Authorization' : access_token}
    )
    assert resp.status_code == 200

    # user1의 tweet에 user2의 tweet이 조회되는지 확인
    resp = api.get(f'/timeline/1')
    tweets = json.loads(resp.data.decode('utf-8'))

    assert resp.status_code == 200
    assert tweets == {
        'user_id' : 1,
        'timeline' : [
            {
                'user_id' : 2,
                'tweet' : 'user2 test tweet'
            }
        ]
    }

def test_unfollow(api):
    # login
    resp = api.post(
        '/login',
        data = json.dumps({'email':'test@test.com', 'password':'1234'}),
        content_type = 'application/json'
    )
    resp_json = json.loads(resp.data.decode('utf-8'))
    access_token = resp_json['access_token']

    # user1(test)가 user2(user) follow
    resp = api.post(
        '/follow',
        data = json.dumps({'id':1, 'follow':2}),
        content_type = 'application/json',
        headers = {'Authorization' : access_token}
    )
    assert resp.status_code == 200

    # user1의 tweet에 user2의 tweet이 조회되는지 확인
    resp = api.get(f'/timeline/1')
    tweets = json.loads(resp.data.decode('utf-8'))

    assert resp.status_code == 200
    assert tweets == {
        'user_id' : 1,
        'timeline' : [
            {
                'user_id' : 2,
                'tweet' : 'user2 test tweet'
            }
        ]
    }

    # unfollow user2(user)
    resp  = api.post(
        '/unfollow',
        data = json.dumps({'id': 1,'unfollow' : 2}),
        content_type = 'application/json',
        headers = {'Authorization' : access_token}
    )
    assert resp.status_code == 200

    # user1(test) tweet에 user2(user)의 tweet이 조회되지 않음을 확인
    resp = api.get(f'/timeline/1')
    tweets = json.loads(resp.data.decode('utf-8'))

    assert resp.status_code == 200
    assert tweets           == {
        'user_id'  : 1,
        'timeline' : [ ]
    }