# auth/auth_manager.py

USERS = {
    "radtech@lungsight.com": {
        "password": "123456",
        "name": "John RadTech",
        "role": "radtech"
    },
    "doctor@lungsight.com": {
        "password": "123456",
        "name": "Dr. Smith",
        "role": "physician"
    }
}


def authenticate(email, password):
    user = USERS.get(email)

    if user and user["password"] == password:
        return {
            "email": email,
            "name": user["name"],
            "role": user["role"]
        }

    return None