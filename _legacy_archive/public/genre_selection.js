document.addEventListener('DOMContentLoaded', function () {
    // 检查登录状态和偏好设置
    const isLoggedIn = localStorage.getItem('isLoggedIn') || sessionStorage.getItem('isLoggedIn');
    const preferences = localStorage.getItem('userPreferences') || sessionStorage.getItem('userPreferences');

    // 如果用户未登录，跳转到登录页
    if (!isLoggedIn) {
        window.location.href = 'login.html';
        return;
    }

    // 如果偏好设置已存在且不为空，直接跳转到首页
    if (preferences && preferences !== 'null' && preferences !== '') {
        window.location.href = 'index.html';
        return;
    }

    // 显示用户名
    const username = localStorage.getItem('username') || sessionStorage.getItem('username') || '番剧爱好者';
    document.getElementById('username').textContent = username;
    document.getElementById('userAvatar').textContent = username.charAt(0).toUpperCase();
    let selectedGenres = [];
    let genresList = [];
    let genreIcons = {}; // 存储图标映射

    // 【修改】获取 genreCarousel 元素
    const genreCarousel = document.getElementById('genreCarousel');
    const carouselTrack = document.getElementById('carouselTrack');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorMessage = document.getElementById('errorMessage');
    const selectedCount = document.getElementById('selectedCount');
    const confirmBtn = document.getElementById('confirmBtn');
    const selectAllBtn = document.getElementById('selectAllBtn');
    const clearBtn = document.getElementById('clearBtn');

    // 配置
    const cardsPerView = 4; // 每页显示的卡片数量（用于按钮点击计算）
    const cardWidth = 180; // 单个卡片的估计宽度（包含 margin）

    // 直接使用文件4中的番剧类型列表
    genresList = [
        "原创", "漫画改", "小说改", "游戏改", "特摄", "布袋戏", "热血", "穿越", "奇幻",
        "战斗", "搞笑", "日常", "科幻", "萌系", "治愈", "校园", "少儿", "泡面",
        "恋爱", "少女", "魔法", "冒险", "历史", "架空", "机战", "神魔", "声控",
        "运动", "励志", "音乐", "推理", "社团", "智斗", "催泪", "美食", "偶像", "乙女", "职场"
    ];

    // 定义类型图标映射
    genreIcons = {
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
        "职场": "fas fa-briefcase"
    };

    // 隐藏加载指示器
    loadingIndicator.style.display = 'none';

    // 动态生成类型卡片
    genresList.forEach(genre => {
        const iconClass = genreIcons[genre] || 'fas fa-question-circle';

        const genreCard = document.createElement('div');
        genreCard.className = 'genre-card';
        genreCard.dataset.genre = genre;

        genreCard.innerHTML = `
            <div class="genre-icon"><i class="${iconClass}"></i></div>
            <div class="genre-name">${genre}</div>
            <div class="checkmark"><i class="fas fa-check"></i></div>
        `;

        genreCard.addEventListener('click', function () {
            const genre = this.dataset.genre;

            if (selectedGenres.includes(genre)) {
                selectedGenres = selectedGenres.filter(g => g !== genre);
                this.classList.remove('selected');
            } else {
                selectedGenres.push(genre);
                this.classList.add('selected');
            }

            updateSelectionInfo();
            confirmBtn.disabled = selectedGenres.length === 0;
        });

        carouselTrack.appendChild(genreCard);
    });

    // 初始化轮播
    initCarousel();

    /**
     * @function initCarousel
     * @description 初始化轮播组件
     */
    function initCarousel() {
        // 更新按钮状态
        updateNavButtons();

        // 添加按钮点击事件
        prevBtn.addEventListener('click', () => moveCarousel(-1));
        nextBtn.addEventListener('click', () => moveCarousel(1));

        // 【新增】监听滚动事件，实时更新按钮状态
        genreCarousel.addEventListener('scroll', updateNavButtons);

        // 【新增】添加鼠标滚轮事件，实现左右滚动
        genreCarousel.addEventListener('wheel', (e) => {
            // e.deltaY > 0 表示向下滚动，e.deltaY < 0 表示向上滚动
            if (e.deltaY !== 0) {
                // 阻止页面的垂直滚动
                e.preventDefault();
                // 将垂直滚动量应用到水平滚动上
                genreCarousel.scrollLeft += e.deltaY;
            }
        });
    }

    /**
     * @function moveCarousel
     * @description 根据方向移动轮播
     * @param {number} direction - 移动方向（-1 表示上一个，1 表示下一个）。
     */
    function moveCarousel(direction) {
        const scrollAmount = direction * cardsPerView * cardWidth;
        genreCarousel.scrollTo({
            left: genreCarousel.scrollLeft + scrollAmount,
            behavior: 'smooth' // 平滑滚动
        });
    }

    /**
     * @function updateNavButtons
     * @description 更新导航按钮的禁用状态
     */
    function updateNavButtons() {
        // 增加 1px 的容差以处理小数像素
        const maxScrollLeft = genreCarousel.scrollWidth - genreCarousel.clientWidth;
        prevBtn.disabled = genreCarousel.scrollLeft <= 0;
        nextBtn.disabled = genreCarousel.scrollLeft >= maxScrollLeft - 1;
    }

    /**
     * @function showError
     * @description 在指定区域显示错误消息。
     * @param {string} message - 要显示的错误消息。
     */
    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
    }

    /**
     * @function updateSelectionInfo
     * @description 更新界面，以反映当前选择的类型数量和“全选”按钮的状态。
     */
    function updateSelectionInfo() {
        const count = selectedGenres.length;
        selectedCount.textContent = `已选择 ${count} 个类型`;

        if (genresList.length > 0 && count === genresList.length) {
            selectAllBtn.textContent = '取消全选';
        } else {
            selectAllBtn.textContent = '全选所有类型';
        }
    }

    // 全选按钮事件
    selectAllBtn.addEventListener('click', function () {
        if (genresList.length === 0) return;

        if (selectedGenres.length === genresList.length) {
            // 取消全选
            selectedGenres = [];
            document.querySelectorAll('.genre-card').forEach(card => {
                card.classList.remove('selected');
            });
        } else {
            // 全选
            selectedGenres = [...genresList];
            document.querySelectorAll('.genre-card').forEach(card => {
                card.classList.add('selected');
            });
        }

        updateSelectionInfo();
        confirmBtn.disabled = selectedGenres.length === 0;
    });

    // 清空按钮事件
    clearBtn.addEventListener('click', function () {
        selectedGenres = [];
        document.querySelectorAll('.genre-card').forEach(card => {
            card.classList.remove('selected');
        });

        updateSelectionInfo();
        confirmBtn.disabled = true;
    });

    // 确认按钮事件
    confirmBtn.addEventListener('click', async function () {
        if (selectedGenres.length > 0) {
            // 保存选择的类型到本地存储
            localStorage.setItem('selectedGenres', JSON.stringify(selectedGenres));
            sessionStorage.setItem('selectedGenres', JSON.stringify(selectedGenres));

            // 获取当前用户名
            const username = localStorage.getItem('username') || sessionStorage.getItem('username') || '';

            // 显示加载状态
            const originalBtnText = confirmBtn.innerHTML;
            confirmBtn.disabled = true;
            confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

            try {
                // 发送请求保存偏好设置
                const response = await fetch('/api/updatePreferences', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        username: username,
                        preferences: selectedGenres
                    })
                });

                const result = await response.json();

                if (result.success) {
                    console.log('偏好设置保存成功');
                    // 更新本地存储的偏好设置
                    if (localStorage.getItem('isLoggedIn')) {
                        localStorage.setItem('userPreferences', JSON.stringify(selectedGenres));
                    } else {
                        sessionStorage.setItem('userPreferences', JSON.stringify(selectedGenres));
                    }

                    // 跳转到首页
                    window.location.href = 'index.html';
                } else {
                    throw new Error(result.message || '保存偏好设置失败');
                }
            } catch (error) {
                console.error('保存偏好设置失败:', error);
                confirmBtn.disabled = false;
                confirmBtn.innerHTML = originalBtnText;
                showError('保存偏好设置失败，请重试');
            }
        }
    });
});