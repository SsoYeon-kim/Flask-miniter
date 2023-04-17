import pytest
import bcrypt
import sys, os, io, json
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import config

from app import create_app
from sqlalchemy import create_engine, text
from unittest import mock

database = create_engine(config.test_config['DB_URL'], encoding= 'utf-8', max_overflow = 0)

# 런타임에 boto3.client 객체를 mock객체로 치환
# app.py에서 import한 boto3모듈을 import (app.boto3)
@pytest.fixture
@mock.patch('app.boto3')
def api(mock_boto3):
    mock_boto3.client.return_value = mock.Mock()
    app = create_app(config.test_config)
    app.config['TEST'] = True
    api = app.test_client()

    return api

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

def test_unauthorized(api):
    # access token 없이 401 리턴 확인
    resp = api.post(
        '/tweet',
        data = json.dumps({'tweet':'test tweet'}),
        content_type = 'application/json'
    )
    assert resp.status_code == 401

    resp = api.post(
        '/follow',
        data = json.dumps({'follow':2}),
        content_type = 'application/json'
    )
    assert resp.status_code == 401

    resp = api.post(
        '/unfollow',
        data = json.dumps({'unfollow':2}),
        content_type = 'application/json'
    )
    assert resp.status_code == 401

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
    tweets = json.loads(resp.data)

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

def test_follow(api):
    # 로그인
    resp = api.post(
        '/login',
        data         = json.dumps({'email' : 'test@test.com', 'password' : '1234'}),
        content_type = 'application/json'
    )
    resp_json    = json.loads(resp.data.decode('utf-8'))
    access_token = resp_json['access_token']

    ## 먼저 유저 1의 tweet 확인 해서 tweet 리스트가 비어 있는것을 확인
    resp   = api.get(f'/timeline/1')
    tweets = json.loads(resp.data.decode('utf-8'))

    assert resp.status_code == 200
    assert tweets           == {
        'user_id'  : 1,
        'timeline' : [ ]
    }

    # follow 유저 아이디 = 2
    resp  = api.post(
        '/follow',
        data         = json.dumps({'follow' : 2}),
        content_type = 'application/json',
        headers      = {'Authorization' : access_token}
    )
    assert resp.status_code == 200

    ## 이제 유저 1의 tweet 확인 해서 유저 2의 tweet의 리턴 되는것을 확인
    resp   = api.get(f'/timeline/1')
    tweets = json.loads(resp.data.decode('utf-8'))

    assert resp.status_code == 200
    assert tweets           == {
        'user_id' : 1,
        'timeline' : [
            {
                'user_id' : 2,
                'tweet'   : "test tweet"
            }
        ]
    }

def test_unfollow(api):
    # 로그인
    resp = api.post(
        '/login',
        data         = json.dumps({"email" : "test@test.com", "password" : "1234"}),
        content_type = 'application/json'
    )
    resp_json    = json.loads(resp.data.decode('utf-8'))
    access_token = resp_json['access_token']

    # follow 유저 아이디 = 2
    resp  = api.post(
        '/follow',
        data         = json.dumps({'follow' : 2}),
        content_type = 'application/json',
        headers      = {'Authorization' : access_token}
    )
    assert resp.status_code == 200

    ## 이제 유저 1의 tweet 확인 해서 유저 2의 tweet의 리턴 되는것을 확인
    resp   = api.get(f'/timeline/1')
    tweets = json.loads(str(resp.data.decode('utf-8')))

    assert resp.status_code == 200
    assert tweets           == {
        "user_id"  : 1,
        "timeline" : [
            {
                "user_id" : 2,
                "tweet"   : "test tweet"
            }
        ]
    }

    # unfollow 유저 아이디 = 2
    resp  = api.post(
        '/unfollow',
        data         = json.dumps({'unfollow' : 2}),
        content_type = 'application/json',
        headers      = {'Authorization' : access_token}
    )
    assert resp.status_code == 200

    ## 이제 유저 1의 tweet 확인 해서 유저 2의 tweet이 더 이상 리턴 되지 않는 것을 확인
    resp   = api.get(f'/timeline/1')
    tweets = json.loads(resp.data.decode('utf-8'))

    assert resp.status_code == 200
    assert tweets           == {
        "user_id"  : 1,
        "timeline" : [ ]
    }

def test_save_and_get_profile_picture(api):
    # 로그인
    resp = api.post(
        '/login',
        data         = json.dumps({"email" : "test@test.com", "password" : "1234"}),
        content_type = 'application/json'
    )
    resp_json    = json.loads(resp.data.decode('utf-8'))
    access_token = resp_json['access_token']

    # 이미지 파일 업로드
    resp = api.post(
        '/profile-picture',
        content_type = 'multipart/form-data',
        headers = {'Authorization' : access_token},
        data = {'profile_pic' : (io.BytesIO(b'some image here'), 'profile.png')}
    )

    assert resp.status_code == 200

    # get image url
    resp = api.get('/profile-picture/1')
    data = json.loads(resp.data.decode('utf-8'))

    assert data['img_url'] == f"{config.test_config['S3_BUCKET_URL']}profile.png"