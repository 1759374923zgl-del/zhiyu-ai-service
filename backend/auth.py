from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity
)
from models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"code": 400, "message": "用户名和密码不能为空"}), 400

    if len(username) < 2 or len(username) > 20:
        return jsonify({"code": 400, "message": "用户名长度须在2-20个字符之间"}), 400

    if len(password) < 6:
        return jsonify({"code": 400, "message": "密码长度不能少于6位"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"code": 400, "message": "该用户名已被占用"}), 400

    user = User(username=username, role="user")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({
        "code": 200,
        "message": "注册成功",
        "data": {
            "token": token,
            "user": user.to_dict()
        }
    })


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"code": 400, "message": "用户名和密码不能为空"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"code": 401, "message": "用户名或密码错误"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({
        "code": 200,
        "message": "登录成功",
        "data": {
            "token": token,
            "user": user.to_dict()
        }
    })


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"code": 404, "message": "用户不存在"}), 404
    return jsonify({"code": 200, "data": user.to_dict()})
