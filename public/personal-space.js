// 页面加载时显示用户信息
document.addEventListener("DOMContentLoaded", function () {
    // 获取存储的用户名
    const username =
        localStorage.getItem("username") ||
        sessionStorage.getItem("username") ||
        "用户";

    document.getElementById("current-user").textContent = username;

    // 获取用户信息
    fetchUserInfo(username);

    // 更改用户喜好按钮
    document
        .getElementById("update-preferences")
        .addEventListener("click", function () {
            const modal = new bootstrap.Modal(
                document.getElementById("preferencesModal")
            );
            modal.show();

            // 初始化模态框中的类型选择
            initPreferencesModal(username);
        });

    // 进入数据分析系统（返回主页面）
    document
        .getElementById("enter-data-analysis")
        .addEventListener("click", function () {
            window.location.href = "index.html";
        });

    // 【新增】处理模态框关闭后的焦点管理，以解决 aria-hidden 警告
    const preferencesModalEl = document.getElementById('preferencesModal');
    const updatePreferencesBtn = document.getElementById('update-preferences');

    preferencesModalEl.addEventListener('hidden.bs.modal', function () {
        // 当模态框完全关闭后，将焦点移回到打开它的按钮上
        updatePreferencesBtn.focus();
    });
});

/**
 * @function initPreferencesModal
 * @description 初始化偏好设置模式，包括获取和显示用户的偏好以及处理偏好更新。
 * @param {string} username - 当前用户的用户名。
 */
function initPreferencesModal(username) {
    const genreGrid = document.querySelector(".genre-grid");
    genreGrid.innerHTML = "";

    // 类型列表
    const genresList = [
        "原创", "漫画改", "小说改", "游戏改", "特摄", "布袋戏", "热血", "穿越", "奇幻",
        "战斗", "搞笑", "日常", "科幻", "萌系", "治愈", "校园", "少儿", "泡面",
        "恋爱", "少女", "魔法", "冒险", "历史", "架空", "机战", "神魔", "声控",
        "运动", "励志", "音乐", "推理", "社团", "智斗", "催泪", "美食", "偶像", "乙女", "职场",
    ];

    // 类型图标映射
    const genreIcons = {
        "原创": "fas fa-lightbulb",
        "漫画改": "fas fa-book",
        "小说改": "fas fa-book-open",
        "游戏改": "fas fa-gamepad",
        "特摄": "fas fa-camera",
        "布袋戏": "fas fa-theater-masks",
        "热血": "fas fa-fire",
        "穿越": "fas fa-door-open",
        "奇幻": "fas fa-dragon",
        "战斗": "fas fa-fist-raised",
        "搞笑": "fas fa-laugh",
        "日常": "fas fa-home",
        "科幻": "fas fa-rocket",
        "萌系": "fas fa-cat",
        "治愈": "fas fa-heart",
        "校园": "fas fa-graduation-cap",
        "少儿": "fas fa-child",
        "泡面": "fas fa-utensils",
        "恋爱": "fas fa-heartbeat",
        "少女": "fas fa-venus",
        "魔法": "fas fa-hat-wizard",
        "冒险": "fas fa-hiking",
        "历史": "fas fa-landmark",
        "架空": "fas fa-cloud",
        "机战": "fas fa-robot",
        "神魔": "fas fa-pastafarianism",
        "声控": "fas fa-microphone-alt",
        "运动": "fas fa-football-ball",
        "励志": "fas fa-trophy",
        "音乐": "fas fa-music",
        "推理": "fas fa-search",
        "社团": "fas fa-users",
        "智斗": "fas fa-brain",
        "催泪": "fas fa-tissue",
        "美食": "fas fa-utensil-spoon",
        "偶像": "fas fa-star",
        "乙女": "fas fa-female",
        "职场": "fas fa-briefcase",
    };

    let selectedGenres = [];

    // 从服务器获取当前用户的偏好设置
    fetchUserPreferences(username)
        .then((preferences) => {
            selectedGenres = preferences || [];
            updateSelectionInfo();

            // 生成类型卡片
            genresList.forEach((genre) => {
                const iconClass = genreIcons[genre] || "fas fa-question-circle";
                const genreCard = document.createElement("div");
                genreCard.className = "genre-card";
                if (selectedGenres.includes(genre)) {
                    genreCard.classList.add("selected");
                }
                genreCard.dataset.genre = genre;
                genreCard.innerHTML = `
                  <div class="genre-icon"><i class="${iconClass}"></i></div>
                  <div class="genre-name">${genre}</div>
                  <div class="checkmark"><i class="fas fa-check"></i></div>
                `;
                genreCard.addEventListener("click", function () {
                    const genre = this.dataset.genre;
                    if (selectedGenres.includes(genre)) {
                        selectedGenres = selectedGenres.filter((g) => g !== genre);
                        this.classList.remove("selected");
                    } else {
                        selectedGenres.push(genre);
                        this.classList.add("selected");
                    }
                    updateSelectionInfo();
                });
                genreGrid.appendChild(genreCard);
            });
        })
        .catch((error) => {
            console.error("获取用户偏好设置失败:", error);
            alert("获取用户偏好设置失败，请重试");
        });

    // 更新选择信息
    function updateSelectionInfo() {
        const count = selectedGenres.length;
        document.getElementById("modalSelectedCount").textContent = `已选择 ${count} 个类型`;
        if (count === genresList.length) {
            document.getElementById("modalSelectAllBtn").textContent = "取消全选";
        } else {
            document.getElementById("modalSelectAllBtn").textContent = "全选所有类型";
        }
    }

    // 全选按钮事件
    document.getElementById("modalSelectAllBtn").addEventListener("click", function () {
        if (selectedGenres.length === genresList.length) {
            selectedGenres = [];
            document.querySelectorAll(".genre-card").forEach((card) => {
                card.classList.remove("selected");
            });
        } else {
            selectedGenres = [...genresList];
            document.querySelectorAll(".genre-card").forEach((card) => {
                card.classList.add("selected");
            });
        }
        updateSelectionInfo();
    });

    // 清空按钮事件
    document.getElementById("modalClearBtn").addEventListener("click", function () {
        selectedGenres = [];
        document.querySelectorAll(".genre-card").forEach((card) => {
            card.classList.remove("selected");
        });
        updateSelectionInfo();
    });

    // 保存按钮事件
    document.getElementById("modalConfirmBtn").addEventListener("click", async function () {
        if (selectedGenres.length === 0) {
            alert("请至少选择一个类型");
            return;
        }
        const loadingOverlay = document.getElementById("loadingOverlay");
        loadingOverlay.style.display = "flex";
        try {
            const response = await fetch("/api/updatePreferences", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({username: username, preferences: selectedGenres}),
            });
            const result = await response.json();
            if (result.success) {
                console.log("偏好设置更新成功");
                if (localStorage.getItem("isLoggedIn")) {
                    localStorage.setItem("userPreferences", JSON.stringify(selectedGenres));
                } else {
                    sessionStorage.setItem("userPreferences", JSON.stringify(selectedGenres));
                }
                document.getElementById("user-preferences").textContent = selectedGenres.join("、");
                const modal = bootstrap.Modal.getInstance(document.getElementById("preferencesModal"));
                modal.hide();
                alert("偏好设置更新成功！");
            } else {
                throw new Error(result.message || "保存偏好设置失败");
            }
        } catch (error) {
            console.error("保存偏好设置失败:", error);
            alert("保存偏好设置失败: " + error.message);
        } finally {
            loadingOverlay.style.display = "none";
        }
    });
}

/**
 * @function fetchUserPreferences
 * @description 从数据库获取用户的偏好设置。
 * @param {string} username - 用户的用户名。
 * @returns {Promise<Array>} - 一个解析为用户偏好数组的 Promise。
 */
function fetchUserPreferences(username) {
    return fetch(`/api/user-info?username=${encodeURIComponent(username)}`)
        .then((response) => response.json())
        .then((data) => {
            if (data.success && data.user && data.user.preferences) {
                return data.user.preferences;
            }
            return [];
        });
}

/**
 * @function fetchUserInfo
 * @description 从数据库获取用户信息并更新网页。
 * @param {string} username - 用户的用户名。
 */
function fetchUserInfo(username) {
    fetch(`/api/user-info?username=${encodeURIComponent(username)}`)
        .then((response) => response.json())
        .then((data) => {
            if (data.success && data.user) {
                const user = data.user;

                // 更新用户信息
                document.getElementById("user-id").textContent = user.id;
                document.getElementById("user-username").textContent = user.username;
                document.getElementById("user-email").textContent = user.email;

                const createdAt = new Date(user.created_at);
                document.getElementById("user-created-at").textContent = `${createdAt.getFullYear()}-` +
                    `${String(createdAt.getMonth() + 1).padStart(2, "0")}-` +
                    `${String(createdAt.getDate()).padStart(2, "0")} ` +
                    `${String(createdAt.getHours()).padStart(2, "0")}:` +
                    `${String(createdAt.getMinutes()).padStart(2, "0")}:` +
                    `${String(createdAt.getSeconds()).padStart(2, "0")}`;

                let preferences = "无偏好设置";
                if (user.preferences && user.preferences.length > 0) {
                    preferences = user.preferences.join("、");
                }
                document.getElementById("user-preferences").textContent = preferences;

            } else {
                console.error("获取用户信息失败:", data.message);
                alert("获取用户信息失败: " + (data.message || "未知错误"));
            }
        })
        .catch((error) => {
            console.error("获取用户信息错误:", error);
            alert("无法连接到服务器");
        });
}