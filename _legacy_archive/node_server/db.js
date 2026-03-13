// db.js
const mysql = require('mysql2');
const {resolve} = require("node:path");
require('dotenv').config({path: resolve(__dirname, '..', '.env')});

// 创建连接池,并使用 promise() 以支持 async/await
const pool = mysql.createPool({
    host: process.env.DB_HOST,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_DATABASE,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
}).promise();

/**
 * 用户登录验证.
 * @param {string} username - 用户名.
 * @param {string} password - 密码.
 * @returns {Promise<object|undefined>} - 如果凭证有效，则返回用户信息对象，否则返回 undefined.
 */
async function authenticateUser(username, password) {
    // 使用 BINARY 关键字确保进行区分大小写的精确字符串匹配
    const query = 'SELECT id, username, email, preferences FROM users WHERE BINARY username = ? AND password = ?';

    try {
        const [rows] = await pool.query(query, [username, password]);

        // 添加查询结果日志，便于调试
        console.log('数据库查询结果:', {
            username,
            results: rows.map(r => ({
                id: r.id,
                username: r.username,
                preferences: r.preferences
            }))
        });

        return rows[0];
    } catch (error) {
        console.error('用户认证查询时出错:', error);
        throw error; // 将错误向上抛出，由调用者处理
    }
}

/**
 * 用户注册.
 * @param {string} username - 用户名.
 * @param {string} email - 邮箱.
 * @param {string} password - 密码.
 * @returns {Promise<number>} - 返回新用户的 ID.
 * @throws {Error} - 如果用户名或邮箱已存在，则抛出错误.
 */
async function registerUser(username, email, password) {
    const query = 'INSERT INTO users (username, email, password) VALUES (?, ?, ?)';

    try {
        const [result] = await pool.query(query, [username, email, password]);
        return result.insertId;
    } catch (error) {
        // 处理唯一约束冲突错误
        if (error.code === 'ER_DUP_ENTRY') {
            const field = error.message.includes('username') ? '用户名' : '邮箱';
            throw new Error(`${field}已存在`);
        }
        console.error('用户注册时出错:', error);
        throw error; // 抛出其他类型的错误
    }
}

/**
 * 更新用户偏好设置.
 * @param {string} username - 需要更新偏好的用户名.
 * @param {object} preferences - 包含偏好设置的JSON对象.
 * @returns {Promise<void>}
 */
async function updateUserPreferences(username, preferences) {
    const query = 'UPDATE users SET preferences = ? WHERE username = ?';

    try {
        // 将 preferences 对象字符串化以便存入数据库
        await pool.query(query, [JSON.stringify(preferences), username]);
    } catch (error) {
        console.error('更新用户偏好时出错:', error);
        throw error;
    }
}

/**
 * 获取用户信息.
 * @param {string} username - 要查询的用户名.
 * @returns {Promise<object|undefined>} - 如果找到用户，则返回用户信息，否则返回 undefined.
 */
async function getUserInfo(username) {
    const query = 'SELECT id, username, email, preferences, created_at FROM users WHERE username = ?';

    try {
        const [rows] = await pool.query(query, [username]);
        return rows[0];
    } catch (error) {
        console.error('获取用户信息时出错:', error);
        throw error;
    }
}

// 测试数据库连接
(async () => {
    try {
        const connection = await pool.getConnection();
        console.log('数据库连接成功');
        connection.release();
    } catch (err) {
        console.error('数据库连接失败:', err);
    }
})();

// 导出所有模块函数
module.exports = {
    authenticateUser,
    registerUser,
    updateUserPreferences,
    getUserInfo,
    pool // 导出 pool 实例，以便在其他需要执行复杂事务的文件中复用
};