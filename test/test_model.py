import bcrypt
import pytest
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import config

from model import UserDao, TweetDao
from sqlalchemy import create_engine, text

database = create_engine(config.test_config['DB_URL'], encoding='utf-8', max_overflow=0)

@pytest.fixture
def user_dao():
    return UserDao(database)

@pytest.fixture
def tweet_dao():
    return TweetDao(database)

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

# 사용자 생성 확인
def get_user(user_id):
    row = database.execute(text("""
        SELECT 
            id,
            name,
            email,
            profile
        FROM users
        WHERE id = :user_id
    """), {
        'user_id' : user_id 
    }).fetchone()

    return {
        'id' : row['id'],
        'name' : row['name'],
        'email' : row['email'],
        'profile' : row['profile']
    } if row else None

# 팔로우 리스트 확인
def get_follow_list(user_id):
    rows = database.execute(text("""
        SELECT follow_user_id as id
        FROM users_follow_list
        WHERE user_id = :user_id
    """), {
        'user_id' : user_id
    }).fetchall()

    return [row['id'] for row in rows]

def test_insert_user(user_dao):
    new_user = {
        'name' : 'new',
        'email' : 'new@test.com',
        'profile' : 'new user profile',
        'password' : '1234'
    } 

    new_user_id = user_dao.insert_user(new_user)
    user = get_user(new_user_id)

    assert user == {
        'id' : new_user_id,
        'name' : new_user['name'],
        'email' : new_user['email'],
        'profile' : new_user['profile']
    }

def test_get_user_id_and_password(user_dao):
    # get_user_id_and_password 메소드를 호출해 유저의 아이디와 비밀번호 해시 값을 읽어옴
    # 유저는 이미 setup_function에서 생성된 유저를 사용
    user_credential = user_dao.get_user_id_and_password(email = 'test@test.com')

    # 유저 아이디 확인
    assert user_credential['id'] == 1
    # 유저 비밀번호 확인
    assert bcrypt.checkpw('1234'.encode('UTF-8'), user_credential['hashed_password'].encode('UTF-8'))

def test_insert_follow(user_dao):
    user_dao.insert_follow(user_id='1', follow_id='2')
    follow_list = get_follow_list(1)

    assert follow_list == [2]

def test_insert_unfollow(user_dao):
    user_dao.insert_follow(user_id='1', follow_id='2')
    user_dao.insert_unfollow(user_id='1', unfollow_id='2')

    folow_list = get_follow_list(1)

    assert folow_list == []

def test_insert_tweet(tweet_dao):
    tweet_dao.insert_tweet(1, 'tweet test')
    timeline = tweet_dao.get_timeline(1)

    assert timeline == [
        {
            'user_id' : 1,
            'tweet' : 'tweet test'
        }  
    ]

def test_timeline(user_dao, tweet_dao):
    tweet_dao.insert_tweet(1, 'first tweet test')
    tweet_dao.insert_tweet(2, 'second tweet test')
    user_dao.insert_follow(1, 2)

    timeline = tweet_dao.get_timeline(1)

    assert timeline == [
        {
            'user_id': 2, 
            'tweet': 'user2 test tweet'
         }, 
        {
            'user_id': 1, 
            'tweet': 'first tweet test'
        }, 
        {
            'user_id': 2, 
            'tweet': 'second tweet test'
        }
    ]