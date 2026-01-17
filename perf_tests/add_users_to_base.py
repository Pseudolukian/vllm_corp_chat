import os
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, Text, BigInteger, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Загрузка переменных окружения из .env файла
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Загружены переменные из {env_path}")
except ImportError:
    print("Предупреждение: python-dotenv не установлен. Используйте: pip install python-dotenv")
    pass

# Настройка подключения к БД
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://openwebui:openwebui@localhost:5432/openwebui"
)

print(f"Подключение к БД: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Создание базового класса для моделей
Base = declarative_base()


class User(Base):
    """Модель пользователя Open WebUI"""
    __tablename__ = "user"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    role = Column(String, default="user")
    profile_image_url = Column(Text, default="/user.png")
    last_active_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    api_key = Column(String, nullable=True)
    settings = Column(Text, nullable=True)
    info = Column(Text, nullable=True)


class Auth(Base):
    """Модель аутентификации Open WebUI"""
    __tablename__ = "auth"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(Text, nullable=False)
    active = Column(Boolean, default=True)


def get_engine():
    """Создание движка базы данных"""
    return create_engine(DATABASE_URL, echo=False)


def get_session():
    """Создание сессии для работы с БД"""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return pwd_context.hash(password)


def generate_user_id(email: str) -> str:
    """Генерация ID пользователя из email"""
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, email))


def add_user_to_db(username: str, email: str, password: str, role: str = "user"):
    """
    Добавление пользователя в базу данных Open WebUI
    
    Args:
        username: Имя пользователя
        email: Email пользователя
        password: Пароль пользователя (будет захеширован)
        role: Роль пользователя (user/admin)
    
    Returns:
        dict: Информация о созданном пользователе или None при ошибке
    """
    session = get_session()
    try:
        user_id = generate_user_id(email)
        current_timestamp = int(datetime.now().timestamp())
        
        # Создание записи пользователя
        user = User(
            id=user_id,
            name=username,
            email=email,
            role=role,
            profile_image_url="/user.png",
            last_active_at=current_timestamp,
            updated_at=current_timestamp,
            created_at=current_timestamp
        )
        
        # Создание записи аутентификации
        auth = Auth(
            id=user_id,
            email=email,
            password=hash_password(password),
            active=True
        )
        
        session.add(user)
        session.add(auth)
        session.commit()
        
        print(f"✓ Пользователь {username} ({email}) успешно добавлен")
        return {
            "id": user_id,
            "username": username,
            "email": email,
            "role": role
        }
    except Exception as e:
        session.rollback()
        print(f"✗ Ошибка при добавлении пользователя {username}: {e}")
        return None
    finally:
        session.close()


def add_users_bulk(users_data: list):
    """
    Массовое добавление пользователей
    
    Args:
        users_data: Список словарей с данными пользователей
                   [{"username": "user1", "email": "user1@example.com", "password": "pass123"}]
    
    Returns:
        dict: Статистика добавления (успешно/ошибки)
    """
    session = get_session()
    success_count = 0
    error_count = 0
    
    for user_data in users_data:
        try:
            username = user_data.get("username")
            email = user_data.get("email")
            password = user_data.get("password")
            role = user_data.get("role", "user")
            
            user_id = generate_user_id(email)
            current_timestamp = int(datetime.now().timestamp())
            
            user = User(
                id=user_id,
                name=username,
                email=email,
                role=role,
                profile_image_url="/user.png",
                last_active_at=current_timestamp,
                updated_at=current_timestamp,
                created_at=current_timestamp
            )
            
            auth = Auth(
                id=user_id,
                email=email,
                password=hash_password(password),
                active=True
            )
            
            session.add(user)
            session.add(auth)
            session.commit()
            
            success_count += 1
            print(f"✓ [{success_count}/{len(users_data)}] {username} ({email})")
        except Exception as e:
            session.rollback()
            error_count += 1
            print(f"✗ Ошибка при добавлении {username}: {e}")
    
    session.close()
    
    print(f"\n{'='*50}")
    print(f"Успешно добавлено: {success_count}")
    print(f"Ошибок: {error_count}")
    print(f"{'='*50}")
    
    return {"success": success_count, "errors": error_count}


def generate_users(count):
    """Генерация списка пользователей"""
    users = []
    user_name = "user"
    password = "password123"
    email_domain = "example.com"
    for i in range(count):
        user = {
            "username": f"{user_name}{i+1}",
            "password": password,
            "email": f"{user_name}{i+1}@{email_domain}"
        }
        users.append(user)
    return users


def main():
    """Основная функция для запуска скрипта"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python add_users_to_base.py <количество_пользователей>")
        print("  python add_users_to_base.py single <username> <email> <password> [role]")
        sys.exit(1)
    
    if sys.argv[1] == "single":
        # Добавление одного пользователя
        if len(sys.argv) < 5:
            print("Ошибка: недостаточно аргументов для добавления пользователя")
            print("Использование: python add_users_to_base.py single <username> <email> <password> [role]")
            sys.exit(1)
        
        username = sys.argv[2]
        email = sys.argv[3]
        password = sys.argv[4]
        role = sys.argv[5] if len(sys.argv) > 5 else "user"
        
        add_user_to_db(username, email, password, role)
    else:
        # Массовое добавление пользователей
        try:
            count = int(sys.argv[1])
            print(f"Генерация и добавление {count} пользователей...\n")
            users = generate_users(count)
            add_users_bulk(users)
        except ValueError:
            print("Ошибка: количество пользователей должно быть числом")
            sys.exit(1)


if __name__ == "__main__":
    main()