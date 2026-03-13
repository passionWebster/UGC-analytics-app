# setup.py
import os
import sys
from getpass import getpass

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import errorcode

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE_PATH = os.path.join(BASE_DIR, '.env')


def interactive_setup():
    """
    交互式安装向导，用于引导用户输入数据库信息并创建 .env 文件。
    """
    print('--- 欢迎使用B站番剧分析系统安装向导 ---')
    print('接下来将引导您完成数据库配置。')

    try:
        db_host = input('请输入 MySQL 主机地址 (默认为: localhost): ').strip() or 'localhost'
        db_user = input('请输入 MySQL 用户名 (默认为: root): ').strip() or 'root'
        # 使用 getpass 安全地输入密码，不会在终端显示
        db_password = getpass('请输入 MySQL 密码: ').strip()
        db_database = input('请输入要创建或使用的数据库名称 (默认为: blibl): ').strip() or 'blibl'

        # 创建 .env 文件并写入内容
        with open(ENV_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(f"# 此文件由安装向导自动生成\n")
            f.write(f"DB_HOST={db_host}\n")
            f.write(f"DB_USER={db_user}\n")
            f.write(f"DB_PASSWORD={db_password}\n")
            f.write(f"DB_DATABASE={db_database}\n\n")
            f.write(f"NODE_PORT=3000\n")
            f.write(f"PYTHON_PORT=5000\n")

        print('\n✅ 配置文件 .env 已成功创建！')
        return True

    except Exception as e:
        print(f'\n[X] 创建 .env 文件时发生错误: {e}')
        return False


def setup_database():
    """
    连接到数据库，并自动创建库和表。
    """
    # 加载 .env 文件中的环境变量
    load_dotenv(ENV_FILE_PATH)
    db_config = {
        'host': os.getenv('DB_HOST'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD')
    }
    db_name = os.getenv('DB_DATABASE')
    connection = None

    try:
        # --- 步骤 1: 连接到 MySQL 服务器 ---
        print(f"[1/3] 正在连接到 MySQL 服务器 at {db_config['host']}...")
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        print('✅ 连接成功！')

        # --- 步骤 2: 创建数据库 ---
        print(f"[2/3] 正在创建数据库 '{db_name}'...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        print(f"✅ 数据库 '{db_name}' 已创建或已存在。")

        # 切换到指定数据库
        connection.database = db_name

        # --- 步骤 3: 创建数据表 ---
        print(f"[3/3] 正在创建 'users' 表...")
        create_table_query = """
                             CREATE TABLE IF NOT EXISTS `users`
                             (
                                 `id`          int          NOT NULL AUTO_INCREMENT,
                                 `username`    varchar(50)  NOT NULL,
                                 `email`       varchar(100) NOT NULL,
                                 `password`    varchar(255) NOT NULL,
                                 `preferences` json              DEFAULT NULL,
                                 `created_at`  timestamp    NULL DEFAULT CURRENT_TIMESTAMP,
                                 PRIMARY KEY (`id`),
                                 UNIQUE KEY `username` (`username`),
                                 UNIQUE KEY `email` (`email`)
                             ) ENGINE = InnoDB
                               DEFAULT CHARSET = utf8mb4
                               COLLATE = utf8mb4_0900_ai_ci; \
                             """
        cursor.execute(create_table_query)
        print("✅ 'users' 表已创建或已存在。")

        print('\n🎉 数据库安装成功完成！')
        return True

    except mysql.connector.Error as err:
        print('\n[X] 数据库安装过程中发生错误:')
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("错误详情: 访问被拒绝。请检查 .env 文件中的 DB_USER 和 DB_PASSWORD 是否正确。")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print(f"错误详情: 数据库 '{db_name}' 不存在。脚本将尝试创建它。")
        else:
            print(f"错误详情: {err}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def main():
    """
    主函数，协调整个安装流程。
    """
    # --- 步骤 1: 检查并创建 .env 文件 ---
    if not os.path.exists(ENV_FILE_PATH):
        if not interactive_setup():
            sys.exit(1)  # 如果交互式设置失败，则退出
    else:
        print('[INFO] 检测到 .env 配置文件，将跳过交互式配置。')

    print("\n--- 开始数据库自动配置 ---")
    if not setup_database():
        sys.exit(1)  # 如果数据库设置失败，则退出

    # 正常完成所有步骤
    sys.exit(0)


if __name__ == "__main__":
    main()
