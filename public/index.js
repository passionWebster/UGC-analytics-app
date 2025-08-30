// index.js
document.addEventListener('DOMContentLoaded', async () => {
    // ------------------- 1. 初始化和认证 -------------------
    const username = localStorage.getItem('username') || sessionStorage.getItem('username');
    if (!username) {
        window.location.href = 'login.html';
        return;
    }
    document.getElementById('username').textContent = username;
    document.getElementById('userAvatar').textContent = username.charAt(0).toUpperCase();

    // ------------------- 2. 全局变量和状态管理 -------------------
    let charts = {};
    let currentAnimeData = null;
    let allRankedAnimes = []; // 【新增】用于存储从 rank_cache.json 获取的全量番剧数据

    // 用于饼图下钻的状态变量
    let isTypeChartDrilledDown = false;
    let typeChartTopLevelData = {};
    let typeChartOtherData = {};

    // 用于偏好推荐的状态变量
    let isPreferenceMode = false; // 偏好模式是否激活
    let userPreferences = []; // 存储从后端获取的用户偏好
    let currentSortBy = 'score'; // 当前的排序标准

    /**
     * @function fetchUserPreferences
     * @description 【新增】获取当前登录用户的偏好设置，并更新全局变量。
     */
    async function fetchUserPreferences() {
        const currentUser = localStorage.getItem('username') || sessionStorage.getItem('username');
        if (!currentUser) {
            console.log("用户未登录，无法获取偏好。");
            return; // 如果未登录，则不执行任何操作
        }
        try {
            const res = await fetch(`http://localhost:3000/api/user-info?username=${currentUser}&t=${new Date().getTime()}`);
            if (res.ok) {
                const data = await res.json();
                // 确保数据结构正确，并更新全局变量
                if (data.user && Array.isArray(data.user.preferences)) {
                    userPreferences = data.user.preferences;
                    console.log("用户偏好已成功获取:", userPreferences);
                } else {
                    userPreferences = []; // 如果没有偏好设置，确保为空数组
                }
            } else {
                console.error("获取用户偏好失败，服务器响应:", res.status);
                userPreferences = [];
            }
        } catch (error) {
            console.error("获取用户偏好时发生网络错误:", error);
            userPreferences = []; // 出错时，确保为空数组
        }
    }

    // ------------------- 2.1 全局通用 ECharts 配置 -------------------
    const commonGrid = {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
    };

    const commonTooltip = {
        trigger: 'axis',
        axisPointer: {
            type: 'cross',
            label: {
                backgroundColor: '#6a7985'
            }
        }
    };
    // ------------------- 3. 功能模块初始化 -------------------

    try {
        await fetchUserPreferences();
        initializeNavigation();
        initializeCustomSelect();
        initializeCharts();
        initializeBangumiSearch();
        await initializeHomepage();
        initializeOverviewModule();
    } catch (error) {
        console.error("初始化时发生错误:", error);
    }


    window.addEventListener('resize', () => {
        setTimeout(() => {
            Object.values(charts).forEach(chart => chart.resize());
        }, 200);
    });

    /**
     * @function ensureElementVisible
     * @description 新增：确保元素可见的辅助函数
     */
    function ensureElementVisible(selector) {
        return new Promise((resolve) => {
            const element = document.querySelector(selector);
            if (!element) {
                resolve(false);
                return;
            }

            // 如果元素已经可见，直接解决
            if (element.offsetParent !== null) {
                resolve(true);
                return;
            }

            // 否则等待一小段时间再检查
            const checkVisibility = () => {
                if (element.offsetParent !== null) {
                    resolve(true);
                } else {
                    setTimeout(checkVisibility, 50);
                }
            };
            checkVisibility();
        });
    }

    /**
     * @function initializeNavigation
     * @description 初始化页面导航功能，包括为导航链接和返回按钮添加事件监听器。
     */
    function initializeNavigation() {
        const navLinks = document.querySelectorAll(".header .nav-link");
        const sections = document.querySelectorAll("main > section");
        const backButtons = document.querySelectorAll(".back-button");

        const showSection = (sectionId) => {
            sections.forEach(section => section.classList.add("d-none"));
            const targetSection = document.getElementById(sectionId);
            if (targetSection) {
                targetSection.classList.remove("d-none");
            }
            navLinks.forEach(navLink => {
                navLink.classList.remove("active");
                if (navLink.getAttribute("href") === `#${sectionId}`) {
                    navLink.classList.add("active");
                }
            });
            setTimeout(() => {
                Object.values(charts).forEach(chart => chart.resize());
            }, 200);
        };

        navLinks.forEach(link => {
            link.addEventListener("click", function (e) {
                e.preventDefault();
                const targetId = this.getAttribute("href").substring(1);
                showSection(targetId);
            });
        });

        backButtons.forEach(btn => btn.addEventListener("click", () => showSection("home")));
        document.getElementById("userInfo").addEventListener("click", () => window.location.href = 'personal-space.html');
        document.getElementById("logoutBtn").addEventListener("click", () => {
            localStorage.clear();
            sessionStorage.clear();
            window.location.href = 'login.html';
        });
    }

    /**
     * @function initializeHomepage
     * @description 【已重构】负责初始化首页所有数据，包括总览卡片和排行榜。
     */
    async function initializeHomepage() {
        // --- 总览卡片数据加载逻辑 ---
        const fetchMonthlyData = async (month) => {
            if (month < 1) return null;
            try {
                const response = await fetch(`http://localhost:5000/api/monthly_data/${month}`);
                if (!response.ok) return null;
                return await response.json();
            } catch (error) {
                return null;
            }
        };

        const calculateGrowth = (current, previous) => {
            if (previous === 0 || !previous || !current) return 0;
            return ((current - previous) / previous) * 100;
        };

        const today = new Date();
        const currentMonth = today.getMonth() + 1;
        const previousMonth = currentMonth === 1 ? 12 : currentMonth - 1;

        const [currentData, previousData] = await Promise.all([
            fetchMonthlyData(currentMonth),
            fetchMonthlyData(previousMonth)
        ]);

        if (currentData) {
            const previousRatio = previousData && previousData.total_views > 0 ? (previousData.total_favorites / previousData.total_views) * 100 : 0;
            const currentRatio = currentData.total_views > 0 ? (currentData.total_favorites / currentData.total_views) * 100 : 0;
            const summaryData = {
                total_anime: {
                    value: currentData.source_bangumi_count || 0,
                    growth: calculateGrowth(currentData.source_bangumi_count, previousData ? previousData.source_bangumi_count : 0)
                },
                total_views: {
                    value: currentData.total_views || 0,
                    growth: calculateGrowth(currentData.total_views, previousData ? previousData.total_views : 0)
                },
                total_favorites: {
                    value: currentData.total_favorites || 0,
                    growth: calculateGrowth(currentData.total_favorites, previousData ? previousData.total_favorites : 0)
                },
                collection_ratio: {value: currentRatio, change: currentRatio - previousRatio}
            };
            updateHomepageCards(summaryData);
        } else {
            console.error("无法加载当前月份的核心数据。");
        }

        // --- 【核心修改】排行榜数据加载和排序逻辑 ---
        await fetchAndInitializeRankList();
    }

    /**
     * @function initializePreferencesTooltip
     * @description 【新增】初始化偏好提示功能，包括为按钮添加悬停提示，并绑定点击事件。
     */
    function initializePreferencesTooltip() {
        const preferencesBtn = document.getElementById("preferencesBtn");
        if (!preferencesBtn) return;

        // 1. 动态创建一次提示框元素
        const tooltip = document.createElement("div");
        tooltip.id = "preferencesTooltip";
        tooltip.className = "preferences-tooltip";
        tooltip.style.display = "none";

        const tooltipContent = document.createElement("div");
        tooltipContent.className = "tooltip-content";
        tooltip.appendChild(tooltipContent);

        preferencesBtn.parentNode.appendChild(tooltip);

        // 2. 绑定事件监听器
        preferencesBtn.addEventListener("mouseenter", () => {
            if (userPreferences.length > 0) {
                tooltipContent.innerHTML = `
                    <i class="fas fa-info-circle me-2"></i>
                    根据您的偏好设置：${userPreferences.join(", ")}。如果需要更改偏好，请移动到个人中心。`;
            } else {
                tooltipContent.innerHTML = `
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    您尚未设置偏好，显示全部推荐`;
            }
            tooltip.style.display = "block";
        });

        preferencesBtn.addEventListener("mouseleave", () => {
            tooltip.style.display = "none";
        });
    }

    /**
     * @function fetchAndInitializeRankList
     * @description 获取番剧排名数据并初始化相关功能。
     */
    async function fetchAndInitializeRankList() {
        const rankContainer = document.getElementById('rank-list-container');
        const sortButtons = document.getElementById('sortButtons');
        const preferencesBtn = document.getElementById('preferencesBtn');

        // --- 1. 初始化悬停提示功能 ---
        initializePreferencesTooltip();

        // --- 2. 统一的渲染入口函数 ---
        const updateRankDisplay = () => {
            let animesToDisplay = [...allRankedAnimes];
            if (isPreferenceMode && userPreferences.length > 0) {
                animesToDisplay = allRankedAnimes.filter(anime =>
                    anime.styles && anime.styles.some(style => userPreferences.includes(style))
                );
            }
            renderRankList(animesToDisplay, currentSortBy);
        };

        // --- 3. 绑定事件监听器 ---
        sortButtons.addEventListener('click', (e) => {
            const button = e.target.closest('button');
            if (button) {
                sortButtons.querySelectorAll('.btn').forEach(btn => {
                    btn.classList.remove('btn-primary', 'active');
                    btn.classList.add('btn-outline-primary');
                });
                button.classList.add('btn-primary', 'active');
                button.classList.remove('btn-outline-primary');
                currentSortBy = button.dataset.sort;
                updateRankDisplay();
            }
        });

        preferencesBtn.addEventListener('click', () => {
            isPreferenceMode = !isPreferenceMode;
            preferencesBtn.classList.toggle('active', isPreferenceMode);
            updateRankDisplay();
        });

        // --- 4. 初始数据加载 ---
        try {
            const response = await fetch('http://localhost:5000/api/rank_cache');
            if (!response.ok) throw new Error('无法加载排名数据');
            const data = await response.json();
            allRankedAnimes = data.list || [];
            updateRankDisplay();
            updateTypeDistributionChart(allRankedAnimes);
            updateReputationPopularityChart(allRankedAnimes);
        } catch (error) {
            console.error('获取排行榜数据失败:', error);
            rankContainer.innerHTML = '<div class="text-center py-5">加载失败，请刷新重试</div>';
        }
    }

    /**
     * @function updateTypeDistributionChart
     * @description 准备饼图数据，包括顶级视图和下钻视图。
     * @param {Array} animes - 包含所有番剧信息的数组。
     */
    function updateTypeDistributionChart(animes) {
        if (!charts['type-distribution'] || !Array.isArray(animes)) return;

        const styleCounts = animes.reduce((acc, anime) => {
            if (anime.styles && Array.isArray(anime.styles)) {
                anime.styles.forEach(style => {
                    acc[style] = (acc[style] || 0) + 1;
                });
            }
            return acc;
        }, {});

        const sortedStyles = Object.entries(styleCounts).sort(([, a], [, b]) => b - a);

        if (sortedStyles.length === 0) {
            typeChartTopLevelData = {seriesData: []};
            typeChartOtherData = {seriesData: []};
            renderTypeDistributionChart();
            return;
        }

        let topLevelSeriesData;
        let otherLevelSeriesData = [];
        const MAX_SLICES = 21;

        if (sortedStyles.length <= MAX_SLICES) {
            topLevelSeriesData = sortedStyles.map(([name, value]) => ({name, value}));
            typeChartOtherData = {seriesData: []};
        } else {
            let numToShow = 4;
            while (numToShow < MAX_SLICES) {
                const topStyles = sortedStyles.slice(0, numToShow);
                const otherCount = sortedStyles.slice(numToShow).reduce((acc, [, count]) => acc + count, 0);
                const smallestTopCount = topStyles[topStyles.length - 1][1];
                if (otherCount <= smallestTopCount) break;
                numToShow++;
            }

            const topData = sortedStyles.slice(0, numToShow);
            const otherItems = sortedStyles.slice(numToShow);
            const otherFinalCount = otherItems.reduce((acc, [, count]) => acc + count, 0);

            topLevelSeriesData = topData.map(([name, value]) => ({name, value}));
            if (otherFinalCount > 0) {
                topLevelSeriesData.push({name: '其他', value: otherFinalCount});
                otherLevelSeriesData = otherItems.map(([name, value]) => ({name, value}));
            }
        }

        typeChartTopLevelData = {seriesData: topLevelSeriesData};
        typeChartOtherData = {seriesData: otherLevelSeriesData};

        isTypeChartDrilledDown = false;
        renderTypeDistributionChart();
    }

    /**
     * @function renderTypeDistributionChart
     * @description 【已更新】根据当前状态渲染饼图，并始终保持左右图例布局。
     */
    function renderTypeDistributionChart() {
        const chart = charts['type-distribution'];
        const controls = document.getElementById('type-distribution-controls'); // 修改ID
        const indicator = document.getElementById('chart-level-indicator');
        if (!chart || !controls || !indicator) return; // 修改变量名

        const dataToShow = isTypeChartDrilledDown ? typeChartOtherData.seriesData : typeChartTopLevelData.seriesData;

        if (!dataToShow || dataToShow.length === 0) {
            chart.setOption({series: [{data: []}], legend: [{}, {}]});
            controls.classList.add('d-none'); // 修改变量名
            return;
        }

        const legendNames = dataToShow.map(item => item.name);
        const midIndex = Math.ceil(legendNames.length / 2);
        const legendDataLeft = legendNames.slice(0, midIndex);
        const legendDataRight = legendNames.slice(midIndex);

        chart.setOption({
            legend: [
                {
                    orient: 'vertical',
                    left: '5%',
                    top: 'center',
                    data: legendDataLeft,
                },
                {
                    orient: 'vertical',
                    right: '5%',
                    top: 'center',
                    data: legendDataRight,
                }
            ],
            series: [{
                data: dataToShow
            }]
        }, {replaceMerge: ['legend']});

        if (isTypeChartDrilledDown) {
            indicator.textContent = '已细分合并的部分'; // 文本可以简化
            controls.classList.remove('d-none'); // 修改变量名
            controls.classList.add('d-flex'); // 确保flex布局生效
        } else {
            controls.classList.add('d-none'); // 修改变量名
            controls.classList.remove('d-flex');
        }
    }

    /**
     * @function updateHomepageCards
     * @description 【已更新】根据传入的数据更新首页的四个总览卡片。
     * @param {object} data - 包含主页卡片所需数据的对象。
     */
    function updateHomepageCards(data) {
        const formatNumber = (num, unit = '') => {
            if (num >= 1e8) return (num / 1e8).toFixed(1) + '亿' + unit;
            if (num >= 1e4) return (num / 1e4).toFixed(1) + '万' + unit;
            if (unit === '%') return num.toFixed(2) + unit;
            return num.toLocaleString() + unit;
        };

        const updateCard = (elementId, value) => document.getElementById(elementId).textContent = value;

        const updateGrowth = (containerId, value, isChange = false) => {
            const container = document.getElementById(containerId);
            if (!container) return;
            // 对于变化值，保留两位小数；对于增长率，保留一位
            const valueFormatted = isChange ? value.toFixed(2) : value.toFixed(1) + '%';
            const iconClass = value >= 0 ? 'fas fa-arrow-up text-success' : 'fas fa-arrow-down text-danger';
            const textClass = value >= 0 ? 'text-success' : 'text-danger';
            container.innerHTML = `<i class="${iconClass}"></i> <span class="${textClass}">${valueFormatted}</span>`;
        };

        updateCard('total-anime', formatNumber(data.total_anime.value));
        updateGrowth('anime-growth-container', data.total_anime.growth);

        updateCard('total-views', formatNumber(data.total_views.value));
        updateGrowth('views-growth-container', data.total_views.growth);

        updateCard('total-followers', formatNumber(data.total_favorites.value));
        updateGrowth('followers-growth-container', data.total_favorites.growth);

        updateCard('average-rating', formatNumber(data.collection_ratio.value, '%'));
        updateGrowth('rating-change-container', data.collection_ratio.change, true);
    }

    /**
     * @function renderRankList
     * @description 纯粹的渲染函数，负责将数据生成HTML，并高亮匹配偏好的标签。
     * @param {Array} animes - 要渲染的番剧对象数组。
     * @param {string} sortBy - 排序依据。
     */
    function renderRankList(animes, sortBy) {
        const container = document.getElementById('rank-list-container');

        if (!Array.isArray(animes) || animes.length === 0) {
            container.innerHTML = `<div class="text-center py-5">${isPreferenceMode ? '没有找到符合您偏好的番剧' : '暂无数据'}</div>`;
            return;
        }

        const sortedAnimes = [...animes].sort((a, b) => {
            const key = sortBy === 'followers' ? 'favorites' : sortBy;
            const valA = key === 'score' ? parseFloat(a[key] || 0) : (a[key] || 0);
            const valB = key === 'score' ? parseFloat(b[key] || 0) : (b[key] || 0);
            return valB - valA;
        });

        const topAnimes = sortedAnimes.slice(0, 10);

        const formatLargeNumber = (num) => {
            if (num >= 1e8) return (num / 1e8).toFixed(1) + '亿';
            if (num >= 1e4) return (num / 1e4).toFixed(1) + '万';
            return num.toLocaleString();
        };

        container.innerHTML = topAnimes.map((anime, index) => {
            const rankClass = index < 3 ? 'top3' : '';
            const proxyUrl = `http://localhost:5000/api/image_proxy?url=${encodeURIComponent(anime.cover)}&title=${encodeURIComponent(anime.title)}&season_id=${anime.season_id}`;

            let displayValue = '';
            let valueIconClass = '';
            switch (sortBy) {
                case 'views':
                    valueIconClass = 'fas fa-play-circle';
                    displayValue = formatLargeNumber(anime.views || 0);
                    break;
                case 'followers':
                    valueIconClass = 'fas fa-heart';
                    displayValue = formatLargeNumber(anime.favorites || 0);
                    break;
                default:
                    valueIconClass = 'fas fa-star';
                    displayValue = `${parseFloat(anime.score || 0).toFixed(1)}分`;
                    break;
            }

            let tagsHtml = '';
            const animeStyles = anime.styles || [];

            if (isPreferenceMode && userPreferences.length > 0) {
                // 1. 分离出匹配的标签和不匹配的标签
                const matchingTags = animeStyles.filter(style => userPreferences.includes(style));
                const otherTags = animeStyles.filter(style => !userPreferences.includes(style));

                // 2. 重新组合，匹配的优先
                const orderedTags = [...matchingTags, ...otherTags];

                // 3. 生成HTML，并为匹配的标签添加高亮样式
                tagsHtml = orderedTags.slice(0, 3).map(tag => {
                    const badgeClass = matchingTags.includes(tag) ? 'badge bg-primary me-1' : 'badge bg-secondary me-1';
                    return `<span class="${badgeClass}">${tag}</span>`;
                }).join('');

            } else {
                // 如果不是偏好模式，则按原逻辑显示
                tagsHtml = animeStyles.slice(0, 3).map(tag => `<span class="badge bg-secondary me-1">${tag}</span>`).join('');
            }

            return `
                <div class="rank-item">
                    <div class="rank-num ${rankClass}">${index + 1}</div>
                    <img src="${proxyUrl}" alt="${anime.title}" class="rank-img">
                    <div class="rank-info">
                        <div class="rank-title">${anime.title}</div>
                        <div class="rank-value">
                            <i class="${valueIconClass} me-1"></i>${displayValue}
                        </div>
                        <div class="rank-tags">${tagsHtml}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * @function updateReputationPopularityChart
     * @description 【新增】处理番剧数据并更新口碑热度分布散点图
     * @param {Array} animes - 包含所有番剧信息的数组
     */
    function updateReputationPopularityChart(animes) {
        const chart = charts['season-trend']; // 获取图表实例
        if (!chart || !Array.isArray(animes)) return;

        try {
            // 1. 数据清洗和格式化
            const chartData = animes
                .map(anime => {
                    const score = parseFloat(anime.score);
                    const favorites = parseInt(anime.favorites, 10);
                    const views = parseInt(anime.views, 10);
                    // 必须有评分和追番数才能在图上展示
                    if (!isNaN(score) && score > 0 && !isNaN(favorites) && favorites > 0) {
                        // 数据结构: [x轴, y轴, ...其他需要在tooltip中显示的数据]
                        return [score, favorites, anime.title, views];
                    }
                    return null;
                })
                .filter(item => item !== null); // 过滤掉无效数据

            // 2. 更新图表
            chart.setOption({
                series: [{
                    data: chartData
                }]
            });

        } catch (error) {
            console.error('更新口碑热度分布图表失败:', error);
        }
    }

    /**
     * @function initializeBangumiSearch
     * @description 【已更新】初始化番剧状态检测模块，并添加图表联动功能。
     */
    function initializeBangumiSearch() {
        const keywordInput = document.getElementById('keyword-input');
        const searchBtn = document.getElementById('search-btn');
        const favoritesCount = document.getElementById('favorites-count');
        const viewsCount = document.getElementById('views-count');
        const statusMessage = document.getElementById('status-message');

        const formatNumber = (num) => {
            if (num === null || num === undefined) return '--';
            if (num < 1e4) return num.toString();
            if (num < 1e8) return (num / 1e4).toFixed(1) + '万';
            return (num / 1e8).toFixed(1) + '亿';
        };

        // 【改动】此函数现在可以处理整个番剧或单集的数据
        const processOnlineHistory = (episodeData) => {
            const timeSlots = [0, 0, 0, 0, 0, 0];
            const slotMap = {"00:00": 0, "04:00": 1, "08:00": 2, "12:00": 3, "16:00": 4, "20:00": 5};

            const episodesToProcess = Array.isArray(episodeData) ? episodeData : [episodeData];

            for (const episode of episodesToProcess) {
                if (episode && episode.online_history && typeof episode.online_history === 'object') {
                    for (const time in episode.online_history) {
                        if (time in slotMap) {
                            timeSlots[slotMap[time]] += episode.online_history[time] || 0;
                        }
                    }
                }
            }
            return timeSlots;
        };

        const performSearch = async () => {
            const keyword = keywordInput.value.trim();
            if (!keyword) {
                statusMessage.textContent = '请输入番剧名进行搜索。';
                return;
            }
            searchBtn.disabled = true;
            searchBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 搜索中...`;
            statusMessage.textContent = `正在为“${keyword}”请求数据...`;
            favoritesCount.textContent = '--';
            viewsCount.textContent = '--';

            try {
                const response = await fetch('http://localhost:5000/search', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({keyword}),
                });
                const result = await response.json();
                if (!response.ok) {
                    // 直接处理失败情况，而不是抛出异常
                    statusMessage.textContent = `错误: ${result.message}`;
                    statusMessage.className = 'form-text mt-2 text-danger';
                    currentAnimeData = null; // 清空数据
                } else {
                    // --- 成功的逻辑保持不变 ---
                    currentAnimeData = result.data;

                    favoritesCount.textContent = formatNumber(currentAnimeData.stats.favorites);
                    viewsCount.textContent = formatNumber(currentAnimeData.stats.views);

                    if (Array.isArray(currentAnimeData.episodes) && currentAnimeData.episodes.length > 0) {
                        const episodeLabels = currentAnimeData.episodes.map(ep => ep.title.replace(/第(\d+)话\s*/, '第$1话\n'));
                        const episodeViews = currentAnimeData.episodes.map(ep => ep.views || 0);

                        charts['play-trend'].setOption({
                            xAxis: {data: episodeLabels, axisLabel: {interval: 0, rotate: 30}},
                            series: [{name: '单集播放量', data: episodeViews}]
                        });
                    } else {
                        charts['play-trend'].setOption({xAxis: {data: []}, series: [{data: []}]});
                    }

                    // 默认显示所有剧集的总和
                    const totalOnlineHistory = processOnlineHistory(currentAnimeData.episodes);
                    charts['watch-time'].setOption({
                        series: [{data: totalOnlineHistory}]
                    });

                    statusMessage.textContent = `成功获取数据。${result.status === 'cached' ? '(来自缓存)' : ''}`;
                    statusMessage.className = 'form-text mt-2 text-success';
                }
            } catch (error) {
                statusMessage.textContent = `错误: ${error.message}`;
                statusMessage.className = 'form-text mt-2 text-danger';
                currentAnimeData = null; // 清空数据
            } finally {
                searchBtn.disabled = false;
                searchBtn.textContent = '搜索';
            }
        };

        searchBtn.addEventListener('click', performSearch);
        keywordInput.addEventListener('keyup', (event) => event.key === 'Enter' && performSearch());

        // --- 【核心新增功能】 ---
        // 为“播放量趋势”图表添加点击事件监听器
        charts['play-trend'].on('click', (params) => {
            // 确保当前有番剧数据，并且点击的是一个数据点
            if (currentAnimeData && currentAnimeData.episodes && params.dataIndex >= 0) {
                const clickedEpisode = currentAnimeData.episodes[params.dataIndex];
                if (clickedEpisode) {
                    // 使用 processOnlineHistory 处理单集数据
                    const singleEpisodeHistory = processOnlineHistory(clickedEpisode);

                    // 更新“观看时间分布”图表
                    charts['watch-time'].setOption({
                        series: [{
                            data: singleEpisodeHistory
                        }]
                    });

                    // (可选) 更新状态消息，提示用户当前显示的是哪一集的数据
                    statusMessage.textContent = `当前显示《${clickedEpisode.title}》的在线人数分布。`;
                    statusMessage.className = 'form-text mt-2 text-info';
                }
            }
        });
    }

    /**
     * @function initCommonControlButtons
     * @description 初始化通用控制按钮。根据容器ID决定是从用户偏好还是从固定列表获取按钮数据。
     */
    function initCommonControlButtons(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        try {
            let buttonsHtml = '';

            // 【核心修改】判断是否是地区维度的按钮容器
            if (containerId === "preference-anime-buttons") {
                const regions = ["国内", "日本", "美国", "其他"];
                buttonsHtml = regions.map((region, index) => {
                    const isActive = index === 0; // 默认激活第一个按钮
                    const value = region === "全部" ? "all" : region; // "全部"对应的值是"all"
                    const buttonClass = isActive ? "btn btn-primary btn-sm active" : "btn btn-outline-secondary btn-sm";
                    return `<button class="${buttonClass}" data-value="${value}">${region}</button>`;
                }).join("");
            } else {
                if (userPreferences.length === 0) {
                    container.innerHTML = '<small class="text-muted">请先在个人中心设置偏好</small>';
                    return;
                }
                buttonsHtml = `<button class="btn btn-primary btn-sm active" data-value="all">所有番剧</button>`;
                buttonsHtml += userPreferences.map(
                    (p) => `<button class="btn btn-outline-secondary btn-sm" data-value="${p}">${p}</button>`
                ).join("");
            }

            container.innerHTML = buttonsHtml;

            // 添加点击事件
            container.addEventListener("click", function (e) {
                if (e.target.tagName === "BUTTON") {
                    container.querySelectorAll(".btn").forEach((btn) => {
                        btn.classList.remove("btn-primary", "active");
                        btn.classList.add("btn-outline-secondary");
                    });

                    e.target.classList.add("btn-primary", "active");
                    e.target.classList.remove("btn-outline-secondary");

                    updateChartBasedOnSelection(containerId, e.target.dataset.value);
                }
            });

        } catch (error) {
            console.error(`初始化 ${containerId} 按钮失败:`, error);
            container.innerHTML = '<div class="text-danger">加载按钮失败</div>';
        }
    }

    /**
     * @function filterAnimeData
     * @description 根据传入的条件筛选番剧数据
     * @param {object} filters - 包含筛选条件的配置对象。
     * @returns {Array} - 经过筛选的番剧数组。
     */
    function filterAnimeData(filters = {}) {
        const {season = 'all', category = 'all', checkExists = []} = filters;

        const seasonMap = {
            'winter': [1, 2, 3], 'spring': [4, 5, 6],
            'summer': [7, 8, 9], 'autumn': [10, 11, 12]
        };

        return allRankedAnimes.filter(anime => {
            // 检查必须存在的字段是否有效
            for (const field of checkExists) {
                const value = anime[field];
                if (!value || value <= 0) return false;
                // 对评分为字符串的情况做特殊处理
                if (field === 'score' && parseFloat(value) <= 0) return false;
            }

            // 按季节筛选
            if (season !== 'all') {
                const releaseDateParts = anime.release_date ? String(anime.release_date).split('-') : [];
                if (releaseDateParts.length < 2) return false;
                const releaseMonth = parseInt(releaseDateParts[1], 10);
                if (isNaN(releaseMonth) || !seasonMap[season].includes(releaseMonth)) return false;
            }

            // 按类型筛选
            if (category !== 'all') {
                if (!Array.isArray(anime.styles) || !anime.styles.includes(category)) return false;
            }

            return true;
        });
    }

    /**
     * @function updateChartBasedOnSelection
     * @description 根据选择更新图表
     */
    function updateChartBasedOnSelection(containerId, selectedValue) {
        // 这里需要根据具体的标签页实现不同的更新逻辑
        if (containerId === "preference-anime-buttons") {
            updatePreferenceChart(selectedValue);
        } else if (containerId === "yearly-control-buttons") {
            updateYearlyChart(selectedValue);
        } else if (containerId === "rating-control-buttons") {
            updateQualityScoreChart(selectedValue);
        }
    }

    /**
     * @function initializeCustomSelect
     * @description 自定义下拉框交互逻辑。
     */
    function initializeCustomSelect() {
        const customSelect = document.querySelector('.custom-select');
        if (!customSelect) return;

        const trigger = customSelect.querySelector('.custom-select-trigger');
        const options = customSelect.querySelectorAll('.custom-option');
        const originalSelect = document.getElementById('collectionInterval');

        // 点击触发器，展开/收起选项
        trigger.addEventListener('click', () => {
            customSelect.classList.toggle('open');
        });

        // 点击选项
        options.forEach(option => {
            option.addEventListener('click', () => {
                // 移除旧的选中状态
                options.forEach(opt => opt.classList.remove('selected'));
                // 添加新的选中状态
                option.classList.add('selected');
                // 更新显示文本
                trigger.querySelector('span').textContent = option.textContent;
                // **关键：同步更新隐藏的真实 <select> 的值**
                originalSelect.value = option.dataset.value;
                // **关键：手动触发 change 事件，让 ECharts 图表更新**
                originalSelect.dispatchEvent(new Event('change'));
                // 关闭下拉
                customSelect.classList.remove('open');
            });
        });

        // 点击外部区域关闭下拉框
        document.addEventListener('click', (e) => {
            if (!customSelect.contains(e.target)) {
                customSelect.classList.remove('open');
            }
        });
    }

    /**
     * @function updatePreferenceChart
     * @description 更新偏好差异图表，计算并展示“地区偏好指数”。
     */
    async function updatePreferenceChart() { // 注意：此函数已无 selectedValue 参数，它会从 DOM 中自行获取
        const chart = charts['preference-diff'];
        if (!chart) return;

        try {
            chart.showLoading();

            if (!allRankedAnimes || allRankedAnimes.length === 0) {
                chart.hideLoading();
                return;
            }

            const globalGenreStats = {};
            allRankedAnimes.forEach(anime => {
                if (anime.styles && Array.isArray(anime.styles)) {
                    anime.styles.forEach(style => {
                        if (!globalGenreStats[style]) {
                            globalGenreStats[style] = {totalFavorites: 0, count: 0};
                        }
                        globalGenreStats[style].totalFavorites += anime.favorites || 0;
                        globalGenreStats[style].count++;
                    });
                }
            });
            for (const style in globalGenreStats) {
                const stats = globalGenreStats[style];
                stats.avgFavorites = stats.count > 0 ? stats.totalFavorites / stats.count : 0;
            }

            const selectedButton = document.querySelector('#preference-anime-buttons .btn.active');
            const selectedRegion = selectedButton ? selectedButton.dataset.value : '国内'; // 默认值改为'国内'

            const regionalAnimes = selectedRegion === 'all'
                ? allRankedAnimes
                : allRankedAnimes.filter(anime => anime.area && anime.area === selectedRegion);

            const regionalGenreStats = {};
            regionalAnimes.forEach(anime => {
                if (anime.styles && Array.isArray(anime.styles)) {
                    anime.styles.forEach(style => {
                        if (!regionalGenreStats[style]) {
                            regionalGenreStats[style] = {totalFavorites: 0, count: 0};
                        }
                        regionalGenreStats[style].totalFavorites += anime.favorites || 0;
                        regionalGenreStats[style].count++;
                    });
                }
            });
            for (const style in regionalGenreStats) {
                const stats = regionalGenreStats[style];
                stats.avgFavorites = stats.count > 0 ? stats.totalFavorites / stats.count : 0;
            }

            const chartData = [];
            for (const style in regionalGenreStats) {
                const regionalStats = regionalGenreStats[style];
                const globalStats = globalGenreStats[style];
                if (regionalStats && globalStats && globalStats.avgFavorites > 0) {
                    const preferenceIndex = regionalStats.avgFavorites / globalStats.avgFavorites;
                    if (regionalStats.count < 3) continue;
                    chartData.push({
                        name: style,
                        value: parseFloat(preferenceIndex.toFixed(2)),
                        regionalAvg: regionalStats.avgFavorites.toFixed(0),
                        globalAvg: globalStats.avgFavorites.toFixed(0),
                        itemStyle: {
                            color: userPreferences.includes(style) ? '#fb7299' : '#87CEFA',
                            borderRadius: 4,
                            borderWidth: 2,
                            borderColor: '#fff',
                            gapWidth: 2
                        }
                    });
                }
            }

            // 更新图表时，并不会修改 preferenceDiffOption 全局变量，而是直接 setOption
            chart.setOption({
                tooltip: { // Tooltip 配置直接在这里定义
                    trigger: 'item',
                    formatter: (params) => {
                        // ############ 主要修改点 1 (针对你提供的参考): 增强对矩形树图 formatter 的安全检查 ############
                        if (!params || !params.data || params.data.value == null) {
                            return ''; // 统一返回空字符串以隐藏提示框
                        }
                        const data = params.data;
                        let comparisonText = '';
                        if (data.value > 1.1) {
                            comparisonText = `<span style="color: #28a745;">(高于全球)</span>`;
                        } else if (data.value < 0.9) {
                            comparisonText = `<span style="color: #dc3545;">(低于全球)</span>`;
                        } else {
                            comparisonText = `<span>(与全球持平)</span>`;
                        }
                        return `<b>${data.name}</b><br/>地区偏好指数: <b style="font-size: 1.2em;">${data.value}</b> ${comparisonText}<br/><hr style="margin: 4px 0;">该地区均追番: ${parseInt(data.regionalAvg).toLocaleString()}<br/>全球平均追番: ${parseInt(data.globalAvg).toLocaleString()}`;
                    }
                },
                series: [{
                    type: 'treemap',
                    roam: false,
                    nodeClick: false,
                    breadcrumb: {show: false},
                    label: {
                        show: true,
                        position: 'inside',
                        formatter: (params) => `${params.name}\n${params.value}`,
                        color: '#fff',
                        fontSize: 14
                    },
                    data: chartData
                }]
            }, {notMerge: true});

        } catch (error) {
            console.error('更新偏好差异图表失败:', error);
        } finally {
            chart.hideLoading();
        }
    }

    /**
     * @function updateYearlyChart
     * @description 更新历年数量变化图表。
     */
    async function updateYearlyChart() {
        const chart = charts['yearly-trend'];
        if (!chart) return;

        if (!allRankedAnimes || allRankedAnimes.length === 0) {
            console.warn("历年番剧数据尚未加载。");
            chart.setOption({xAxis: {data: []}, series: []});
            return;
        }

        const selectedButton = document.querySelector('#yearly-control-buttons .btn.active');
        const selectedCategory = selectedButton ? selectedButton.dataset.value : 'all';

        try {
            chart.showLoading();

            const filteredAnimes = filterAnimeData({category: selectedCategory});

            const yearlyData = {};

            filteredAnimes.forEach(anime => {
                if (anime.release_date && typeof anime.release_date === 'string') {
                    const dateParts = anime.release_date.split('-');
                    if (dateParts.length < 2) return;

                    const year = dateParts[0];
                    const month = parseInt(dateParts[1], 10);

                    if (!yearlyData[year]) {
                        yearlyData[year] = [0, 0, 0, 0];
                    }

                    // 月份到季度的映射
                    if (month >= 1 && month <= 3) yearlyData[year][0]++;
                    else if (month >= 4 && month <= 6) yearlyData[year][1]++;
                    else if (month >= 7 && month <= 9) yearlyData[year][2]++;
                    else if (month >= 10 && month <= 12) yearlyData[year][3]++;
                }
            });

            const legendData = Object.keys(yearlyData).sort((a, b) => b - a);
            const seriesData = legendData.map(year => ({
                name: year,
                type: 'line',
                smooth: true,
                data: yearlyData[year]
            }));

            const xData = ['春季(1-3月)', '夏季(4-6月)', '秋季(7-9月)', '冬季(10-12月)'];

            chart.setOption({
                tooltip: commonTooltip,
                xAxis: {
                    data: xData
                },
                yAxis: {
                    type: 'value',
                    name: '番剧数量'
                },
                legend: {
                    data: legendData
                },
                series: seriesData
            }, {notMerge: true});

        } catch (error) {
            console.error('更新历年数量图表失败:', error);
        } finally {
            chart.hideLoading();
        }
    }

    /**
     * @function updateQualityScoreChart
     * @description 计算并更新“口碑热度指数”图表。
     */
    async function updateQualityScoreChart() {
        const chart = charts['collection-ratio']; // 沿用旧的chart实例
        if (!chart || !allRankedAnimes || allRankedAnimes.length === 0) {
            return;
        }

        chart.showLoading();

        // --- 1. 数据处理 ---
        const selectedButton = document.querySelector('#rating-control-buttons .btn.active');
        const selectedCategory = selectedButton ? selectedButton.dataset.value : 'all';
        const selectedSeason = document.getElementById('collectionInterval').value;

        // 使用重构的公共函数进行筛选
        let processedData = filterAnimeData({
            season: selectedSeason,
            category: selectedCategory,
            checkExists: ['score', 'views', 'favorites'] // 检查这些字段必须存在且>0
        });

        // 计算“口碑热度指数”
        processedData.forEach(anime => {
            anime.qualityScore = parseFloat(anime.score) * Math.log10(anime.favorites) * Math.log10(anime.views);
        });

        // 排序并截取Top 15
        const topAnimes = processedData
            .filter(anime => !isNaN(anime.qualityScore))
            .sort((a, b) => b.qualityScore - a.qualityScore)
            .slice(0, 15);

        const yAxisData = topAnimes.map(anime => anime.title).reverse();
        const seriesData = topAnimes.map(anime => ({
            value: parseFloat(anime.qualityScore.toFixed(0)), // 指数取整
            score: anime.score,
            views: anime.views,
            favorites: anime.favorites
        })).reverse();

        // --- 2. 在函数内部构建完整的图表配置对象 ---
        const fullOption = {
            tooltip: {
                trigger: 'axis',
                axisPointer: {type: 'shadow'},
                backgroundColor: 'rgba(30, 41, 59, 0.9)',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                textStyle: {color: '#f0f0f0'},
                formatter: function (params) {
                    if (!params || params.length === 0) return '';
                    const data = params[0].data;
                    const formatNumber = (num) => {
                        if (!num) return '0';
                        if (num >= 1e8) return (num / 1e8).toFixed(2) + ' 亿';
                        if (num >= 1e4) return (num / 1e4).toFixed(1) + ' 万';
                        return num.toLocaleString();
                    };
                    return `<b>${params[0].name}</b><br/>
                            <span style="font-size:1.2em; color:#fde047; font-weight:bold;">口碑热度指数: ${formatNumber(data.value)}</span><br/>
                            <hr style="margin: 4px 0; border-color: rgba(255, 255, 255, 0.2);">
                            B站评分: ${data.score}<br/>
                            追番数: ${formatNumber(data.favorites)}<br/>
                            播放量: ${formatNumber(data.views)}`;
                }
            },
            grid: {...commonGrid, left: '5%', right: '10%'},
            xAxis: {
                type: 'value',
                name: '口碑热度指数'
            },
            yAxis: {
                type: 'category',
                data: yAxisData,
                axisLabel: {show: false},
                axisTick: {show: false},
                axisLine: {show: false}
            },
            series: [{
                name: '口碑热度指数',
                type: 'bar',
                barWidth: '60%',
                data: seriesData,
                itemStyle: {
                    borderRadius: [0, 5, 5, 0],
                    color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        {offset: 0, color: '#f97316'}, // 橙色
                        {offset: 1, color: '#facc15'}  // 黄色
                    ])
                },
                emphasis: {
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                            {offset: 0, color: '#fb923c'},
                            {offset: 1, color: '#fde047'}
                        ])
                    }
                }
            }]
        };

        // --- 3. 使用完整的配置更新图表 ---
        chart.setOption(fullOption, {notMerge: true});
        chart.hideLoading();
    }

    /**
     * @function updateStyleCombinationChart
     * @description 分析并更新“热门风格组合”图表。
     */
    async function updateStyleCombinationChart() {
        const chart = charts['category-trend'];
        if (!chart || !allRankedAnimes || allRankedAnimes.length === 0) {
            return;
        }

        // --- 事件解绑，防止重复监听 ---
        chart.off('click');

        chart.showLoading();

        // --- 数据处理部分 (携带更多信息) ---
        const combinations = {};
        allRankedAnimes.forEach(anime => {
            if (Array.isArray(anime.styles) && anime.styles.length >= 2) {
                const styles = [...anime.styles].sort();
                for (let i = 0; i < styles.length; i++) {
                    for (let j = i + 1; j < styles.length; j++) {
                        const comboKey = `${styles[i]} + ${styles[j]}`;
                        if (!combinations[comboKey]) {
                            combinations[comboKey] = {totalFavorites: 0, count: 0, animes: []};
                        }
                        const favorites = Number(anime.favorites) || 0;
                        combinations[comboKey].totalFavorites += favorites;
                        combinations[comboKey].count++;
                        // 携带更完整的番剧对象
                        combinations[comboKey].animes.push({
                            title: anime.title,
                            cover: anime.cover,
                            score: anime.score,
                            favorites: anime.favorites,
                            season_id: anime.season_id
                        });
                    }
                }
            }
        });

        const minAnimeCount = 5;
        const topCombinations = Object.entries(combinations)
            .map(([name, data]) => ({
                name,
                count: data.count,
                avgFavorites: data.count > 0 ? data.totalFavorites / data.count : 0,
                animes: data.animes.sort((a, b) => (b.favorites || 0) - (a.favorites || 0)) // 按追番数排序
            }))
            .filter(combo => combo.count >= minAnimeCount)
            .sort((a, b) => b.avgFavorites - a.avgFavorites)
            .slice(0, 20);

        const seriesData = topCombinations.map(combo => ({
            name: combo.name,
            value: Math.round(combo.avgFavorites),
            count: combo.count,
            animes: combo.animes
        }));

        const fullOption = {
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(30, 41, 59, 0.9)',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                textStyle: {color: '#f0f0f0'},
                formatter: function (params) {
                    if (!params.data || params.data.value == null) return '数据无效';
                    const {name, value, count, animes} = params.data;
                    const formatNumber = (num) => num ? num.toLocaleString() : 'N/A';
                    let animeListHtml = '';
                    if (animes && animes.length > 0) {
                        const displayAnimes = animes.slice(0, 5);
                        animeListHtml = displayAnimes.map(anime => `<li>${anime.title || '未知标题'}</li>`).join('');
                        if (animes.length > 5) {
                            animeListHtml += `<li>等 ${animes.length} 部番剧...</li>`;
                        }
                        animeListHtml = `<hr style="margin: 4px 0; border-color: rgba(255, 255, 255, 0.2);">
                                         <span style="color:#d1d5db;">包含番剧 (部分):</span><ul style="padding-left: 15px; margin-top: 5px; margin-bottom: 0;">${animeListHtml}</ul>`;
                    }
                    return `<b>${name}</b><br/>
                            <span style="font-size:1.2em; color:#34d399; font-weight:bold;">平均追番: ${formatNumber(value)}</span><br/>
                            <hr style="margin: 4px 0; border-color: rgba(255, 255, 255, 0.2);">
                            包含番剧数: ${count}${animeListHtml}`;
                }
            },
            series: [{
                type: 'treemap',
                // 【关键修改】将 roam 设置为 false
                // 这将禁用图表的缩放（鼠标滚轮）和拖拽（鼠标指针）功能
                roam: false,
                nodeClick: false,
                breadcrumb: {show: false},
                label: {
                    show: true,
                    position: 'inside',
                    formatter: '{b}',
                    color: '#fff',
                    fontSize: 14,
                    fontWeight: 'bold'
                },
                itemStyle: {gapWidth: 3, borderColor: '#fff', borderRadius: 5},
                data: seriesData
            }]
        };

        chart.setOption(fullOption, {notMerge: true});
        chart.hideLoading();


        const chartContainer = document.querySelector('#category .chart-container');
        const detailPanel = chartContainer.querySelector('.combo-detail-panel');
        const closeBtn = detailPanel.querySelector('.btn-close-detail');

        chart.on('click', (params) => {
            if (params.data) {
                const {name, value, count, animes} = params.data;

                if (!animes) {
                    return;
                }

                // 隐藏主图表的Tooltip并禁用其事件
                chart.dispatchAction({type: 'hideTip'});
                chart.setOption({series: [{silent: true}]});

                // 【新增修改】直接操作DOM来更新新的头部数据块
                const detailBlock = document.getElementById('detail-block');
                const detailBlockTitle = document.getElementById('detail-block-title');

                // 1. 更新头部数据块的背景色和标题
                detailBlock.style.backgroundColor = params.color;
                detailBlockTitle.textContent = name;

                // 2. 填充详情面板 (逻辑微调，使用 name 变量)
                detailPanel.querySelector('#detail-title').textContent = name;
                detailPanel.querySelector('#detail-stats').textContent = `共 ${count} 部番剧 · 平均追番 ${value.toLocaleString()}`;

                const animeListContainer = detailPanel.querySelector('.detail-anime-list');

                const formatLargeNumber = (num) => {
                    if (num === null || num === undefined) return 'N/A';
                    if (num >= 1e8) return (num / 1e8).toFixed(1) + '亿';
                    if (num >= 1e4) return (num / 1e4).toFixed(1) + '万';
                    return num.toLocaleString();
                };

                animeListContainer.innerHTML = animes.map((anime, index) => {
                    const proxyUrl = `http://localhost:5000/api/image_proxy?url=${encodeURIComponent(anime.cover)}&title=${encodeURIComponent(anime.title)}&season_id=${anime.season_id}`;
                    return `
                    <div class="detail-anime-item">
                        <span class="rank">${index + 1}</span>
                        <img src="${proxyUrl}" alt="${anime.title}" class="cover">
                        <div class="info">
                            <h5>${anime.title}</h5>
                            <p>
                                <i class="fas fa-star"></i> ${anime.score || '暂无评分'} · 
                                <i class="fas fa-heart"></i> ${formatLargeNumber(anime.favorites)}
                            </p>
                        </div>
                    </div>
                `;
                }).join('');

                // 3. 触发CSS动画
                chartContainer.classList.add('detail-view-active');
            }
        });
        // 4. 关闭详情视图
        closeBtn.onclick = () => {
            chartContainer.classList.remove('detail-view-active');
            chart.setOption({
                series: [{
                    silent: false
                }]
            });
        };
    }

    /**
     * @function initializeOverviewModule
     * @description 初始化概述模块，包括为各种交互元素添加事件监听器并更新图表。
     */
    function initializeOverviewModule() {
        // --- 1. 为所有控制元素（下拉框）绑定事件监听器 ---
        // 收藏占比
        document.getElementById('collectionInterval').addEventListener('change', updateQualityScoreChart);

        // 注意：按钮组的点击事件已在 initCommonControlButtons 和 initCategoryTrendButtons 中统一处理
        initCommonControlButtons("preference-anime-buttons");
        initCommonControlButtons("yearly-control-buttons");
        initCommonControlButtons("rating-control-buttons");
        // ...

        // --- 3. 初始化默认图表状态 ---
        // 确保在按钮和图表都初始化完毕后，加载一次默认数据
        setTimeout(() => {
            updateYearlyChart();
            updatePreferenceChart();
            updateQualityScoreChart();
            updateStyleCombinationChart();
        }, 500);


        // --- 4. 处理标签页切换时的图表大小调整 ---
        document.querySelectorAll('#overviewTabs button[data-bs-toggle="pill"]').forEach(tabEl => {
            tabEl.addEventListener("shown.bs.tab", async (event) => {
                const targetId = event.target.dataset.bsTarget.substring(1);

                // 确保图表容器可见后再调整图表大小
                await ensureElementVisible(`#${targetId}`);

                // 为所有图表添加延迟调整，确保DOM完全渲染
                setTimeout(() => {
                    Object.values(charts).forEach(chart => chart.resize());
                }, 100);
            });
        });

        // 初始激活的标签页也需要调整
        setTimeout(() => {
            Object.values(charts).forEach(chart => chart.resize());
        }, 500);
    }

    /**
     * @function initializeCharts
     * @description 初始化页面上所有的 ECharts 实例。
     * 该函数现在使用更清晰的结构和共享配置来创建图表。
     */
    function initializeCharts() {

        // --- 初始化函数 ---
        const initChart = (id, option) => {
            const element = document.getElementById(id);
            if (element) {
                try {
                    // 如果元素上已有 ECharts 实例，先销毁它
                    const existingChart = echarts.getInstanceByDom(element);
                    if (existingChart) {
                        existingChart.dispose();
                    }
                    const chart = echarts.init(element);
                    chart.setOption(option);
                    charts[id.replace('chart-', '')] = chart;
                    return chart;
                } catch (e) {
                    console.error(`初始化图表失败: ${id}`, e);
                }
            }
        };

        // --- 各图表具体配置 ---

        // 首页 - 类型分布（饼图）
        const typeDistributionOption = {
            tooltip: {
                trigger: "item",
                formatter: (params) => {
                    if (!params || params.value == null || params.name == null) {
                        return ''; // 返回空字符串，隐藏提示框
                    }
                    // params.marker 是提示框前面的小圆点
                    const defaultFormat = `${params.marker}${params.name}: ${params.value} (${params.percent}%)`;

                    // 如果鼠标悬停的切片名称是“其他”
                    if (params.name === '其他') {
                        // 在默认提示信息的下方添加一行小字提示
                        return `${defaultFormat}<br><small style="color: #999; margin-left: 18px;">点击可查看细分</small>`;
                    }

                    // 对于其他切片，保持默认样式
                    return defaultFormat;
                }
            },
            legend: [
                {
                    orient: 'vertical',
                    left: '5%',
                    top: 'center',
                    data: [],
                },
                {
                    orient: 'vertical',
                    right: '5%',
                    top: 'center',
                    data: [],
                }
            ],
            series: [{
                name: '类型分布',
                type: "pie",
                radius: ["35%", "60%"],
                center: ['50%', '50%'],
                avoidLabelOverlap: false,
                itemStyle: {borderRadius: 10, borderColor: '#fff', borderWidth: 2},
                label: {show: false, position: 'center'},
                emphasis: {
                    label: {show: true, fontSize: '20', fontWeight: 'bold'}
                },
                labelLine: {show: false},
                data: []
            }]
        };

        const typeChart = initChart('chart-type-distribution', typeDistributionOption);
        if (typeChart) {
            // 【新增】为饼图绑定点击事件
            typeChart.on('click', (params) => {
                // 如果当前是顶级视图，且点击的是“其他”，并且“其他”确实有数据
                if (!isTypeChartDrilledDown && params.name === '其他' && typeChartOtherData.seriesData.length > 0) {
                    typeChart.dispatchAction({type: 'hideTip'});
                    isTypeChartDrilledDown = true;
                    renderTypeDistributionChart();
                }
            });

            // 【新增】为返回按钮绑定事件
            document.getElementById('back-to-main-chart').addEventListener('click', () => {
                if (isTypeChartDrilledDown) {
                    isTypeChartDrilledDown = false;
                    renderTypeDistributionChart();
                }
            });
        }

        // 首页 - 口碑热度分布（散点图）
        const reputationPopularityOption = {
            tooltip: {
                trigger: 'item',
                axisPointer: {
                    type: 'cross'
                },
                formatter: function (params) {
                    if (params.value) {
                        // params.value 的数据结构: [评分, 追番数, '标题', 播放量]
                        const title = params.value[2];
                        const score = params.value[0];
                        const followers = params.value[1];
                        const views = params.value[3];
                        const formattedFollowers = followers >= 10000 ? (followers / 10000).toFixed(1) + '万' : followers;
                        const formattedViews = views >= 10000 ? (views / 10000).toFixed(1) + '万' : views;

                        return `${params.marker}<b>${title}</b><br/>
                        评分: <b>${score}</b><br/>
                        追番: <b>${formattedFollowers}</b><br/>
                        播放: <b>${formattedViews}</b>`;
                    }
                    return '无数据';
                }
            },
            grid: commonGrid,
            xAxis: {
                type: 'value',
                name: '评分',
                nameLocation: 'middle',
                nameGap: 25,
                splitLine: {
                    lineStyle: {
                        type: 'dashed'
                    }
                },
                min: 7 // 聚焦于7分以上的作品，使分布更有意义
            },
            yAxis: {
                type: 'log', // 使用对数轴，避免高热度作品压缩其他数据点
                name: '追番人数',
                splitLine: {
                    lineStyle: {
                        type: 'dashed'
                    }
                }
            },
            series: [{
                name: '番剧',
                type: 'scatter',
                symbolSize: 10,
                data: [], // 等待动态数据填充
                emphasis: {
                    focus: 'series',
                    label: {
                        show: true,
                        formatter: function (params) {
                            return params.value[2]; // 鼠标悬停时显示番剧标题
                        },
                        position: 'top'
                    }
                }
            }]
        };

        // 番剧状态检测 - 播放量趋势（面积图）
        const playTrendOption = {
            tooltip: commonTooltip,
            grid: {...commonGrid, bottom: "10%"}, // 增加底部边距以容纳旋转的标签
            xAxis: {
                type: "category",
                boundaryGap: false,
                axisLabel: {show: false}, // 隐藏标签
                data: [] // 等待动态数据
            },
            yAxis: {type: "value", name: "单集播放量"},
            series: [{
                name: "单集播放量",
                type: "line",
                areaStyle: {},
                smooth: true,
                data: [] // 等待动态数据
            }]
        };

        // 番剧状态检测 - 观看时间分布（柱状图）
        const watchTimeOption = {
            tooltip: commonTooltip,
            grid: commonGrid,
            xAxis: {type: 'category', data: ['0-4点', '4-8点', '8-12点', '12-16点', '16-20点', '20-24点']},
            yAxis: {type: 'value', name: "总在线人数"},
            series: [{
                name: '观看分布',
                type: 'bar',
                barWidth: '60%',
                data: [0, 0, 0, 0, 0, 0] // 初始数据
            }]
        };

        // 番剧概览 - 年度上新趋势（折线图）
        const yearlyTrendOption = {
            tooltip: commonTooltip,
            grid: {...commonGrid, bottom: '15%'}, // 为图例增加底部空间
            xAxis: {type: 'category', data: []},
            yAxis: {type: 'value', name: '上新数量'},
            legend: { // 新增图例配置
                data: [],
                bottom: 0,
                type: 'scroll' // 如果年份过多，图例可以滚动
            },
            series: [] // 初始为空，将动态填充多条折线
        };


        // 番剧概览 - 用户偏好差异（矩形树图）
        const preferenceDiffOption = {
            tooltip: {trigger: 'item'},
            series: [{
                type: 'treemap',
                roam: false,
                nodeClick: false,
                breadcrumb: {show: false},
                label: {show: true, position: 'inside', formatter: '{b}\n{c}'},
                itemStyle: {
                    gapWidth: 2
                },
                data: [] // 等待动态数据
            }]
        };

        // 番剧概览 - 口碑热度指数（水平条形图）
        const collectionRatioOption = {
            tooltip: {
                trigger: 'axis',
                axisPointer: {type: 'shadow'}
            },
            grid: {...commonGrid, left: '25%', right: '10%'},
            xAxis: {
                type: 'value',
                name: '口碑热度指数'
            },
            yAxis: {
                type: 'category',
                data: [],
                axisLabel: {show: false}
            },
            series: [{
                name: '口碑热度指数',
                type: 'bar',
                data: []
            }]
        };

        // 番剧概览 - 热门风格组合（矩形树图）
        const categoryTrendOption = {
            tooltip: {trigger: 'item'},
            series: [{
                type: 'treemap',
                data: []
            }]
        };

        // --- 批量执行初始化 ---
        initChart('chart-season-trend', reputationPopularityOption);
        initChart('chart-play-trend', playTrendOption);
        initChart('chart-watch-time', watchTimeOption);
        initChart('chart-yearly-trend', yearlyTrendOption);
        initChart('chart-preference-diff', preferenceDiffOption);
        initChart('chart-collection-ratio', collectionRatioOption);
        initChart('chart-category-trend', categoryTrendOption);
    }
});