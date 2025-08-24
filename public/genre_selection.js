document.addEventListener('DOMContentLoaded', function() {
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
    
    const carouselTrack = document.getElementById('carouselTrack');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const carouselDots = document.getElementById('carouselDots');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorMessage = document.getElementById('errorMessage');
    const selectedCount = document.getElementById('selectedCount');
    const confirmBtn = document.getElementById('confirmBtn');
    const selectAllBtn = document.getElementById('selectAllBtn');
    const clearBtn = document.getElementById('clearBtn');
    
    // 配置
    const cardsPerView = 5; // 每页显示的卡片数量
    let currentPosition = 0;
    let cardWidth = 180; // 卡片宽度（包含margin）
    let maxPosition = 0;
    
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
        
        genreCard.addEventListener('click', function() {
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
    
    function initCarousel() {
        // 计算轮播参数
        const cardCount = genresList.length;
        const carouselWidth = carouselTrack.scrollWidth;
        const visibleWidth = document.querySelector('.genre-carousel').offsetWidth;
        maxPosition = Math.max(0, carouselWidth - visibleWidth);
        
        // 创建轮播点
        createDots();
        
        // 更新按钮状态
        updateNavButtons();
        
        // 添加轮播事件
        prevBtn.addEventListener('click', () => moveCarousel(-1));
        nextBtn.addEventListener('click', () => moveCarousel(1));
        
        // 添加触摸滑动支持
        let startX = 0;
        let isDragging = false;
        
        carouselTrack.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            isDragging = true;
        });
        
        carouselTrack.addEventListener('touchmove', (e) => {
            if (!isDragging) return;
            const diffX = e.touches[0].clientX - startX;
            // 暂时移动轨道
            carouselTrack.style.transform = `translateX(${currentPosition + diffX}px)`;
        });
        
        carouselTrack.addEventListener('touchend', (e) => {
            if (!isDragging) return;
            isDragging = false;
            
            const endX = e.changedTouches[0].clientX;
            const diffX = endX - startX;
            
            // 根据滑动距离决定是否翻页
            if (Math.abs(diffX) > 50) {
                if (diffX > 0) {
                    moveCarousel(-1); // 向右滑动，显示上一页
                } else {
                    moveCarousel(1); // 向左滑动，显示下一页
                }
            } else {
                // 恢复原位
                carouselTrack.style.transform = `translateX(${-currentPosition}px)`;
            }
        });
    }
    
    // 创建轮播点
    function createDots() {
        carouselDots.innerHTML = '';
        const dotCount = Math.ceil(genresList.length / cardsPerView);
        
        for (let i = 0; i < dotCount; i++) {
            const dot = document.createElement('div');
            dot.className = 'carousel-dot';
            if (i === 0) dot.classList.add('active');
            dot.addEventListener('click', () => {
                moveToPosition(i * cardsPerView * cardWidth);
            });
            carouselDots.appendChild(dot);
        }
    }
    
    // 移动轮播
    function moveCarousel(direction) {
        // 计算新位置
        let newPosition = currentPosition + (direction * cardsPerView * cardWidth);
        
        // 限制位置范围
        newPosition = Math.max(0, Math.min(newPosition, maxPosition));
        
        // 应用新位置
        carouselTrack.style.transform = `translateX(${-newPosition}px)`;
        currentPosition = newPosition;
        
        // 更新按钮状态
        updateNavButtons();
        
        // 更新轮播点
        updateDots();
    }
    
    // 移动到指定位置
    function moveToPosition(position) {
        position = Math.max(0, Math.min(position, maxPosition));
        carouselTrack.style.transform = `translateX(${-position}px)`;
        currentPosition = position;
        updateNavButtons();
        updateDots();
    }
    
    // 更新导航按钮状态
    function updateNavButtons() {
        prevBtn.disabled = currentPosition <= 0;
        nextBtn.disabled = currentPosition >= maxPosition;
    }
    
    // 更新轮播点状态
    function updateDots() {
        const dots = document.querySelectorAll('.carousel-dot');
        const activeIndex = Math.floor(currentPosition / (cardsPerView * cardWidth));
        
        dots.forEach((dot, index) => {
            dot.classList.toggle('active', index === activeIndex);
        });
    }
    
    // 显示错误信息
    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
    }
    
    // 更新选择信息
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
    selectAllBtn.addEventListener('click', function() {
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
    clearBtn.addEventListener('click', function() {
        selectedGenres = [];
        document.querySelectorAll('.genre-card').forEach(card => {
            card.classList.remove('selected');
        });
        
        updateSelectionInfo();
        confirmBtn.disabled = true;
    });
    
    confirmBtn.addEventListener('click', async function() {
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