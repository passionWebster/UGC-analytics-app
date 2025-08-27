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

    // ------------------- 3. 功能模块初始化 -------------------

    try {
        initializeNavigation();
        initializeCharts();
        initializeBangumiSearch();
        initializeOverviewModule();
        await initializeHomepage();
    } catch (error) {
        console.error("初始化时发生错误:", error);
    }


    window.addEventListener('resize', () => {
        setTimeout(() => {
            Object.values(charts).forEach(chart => chart.resize());
        }, 200);
    });

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
        preferencesBtn.addEventListener("mouseenter", async () => {
            const currentUser = localStorage.getItem('username') || sessionStorage.getItem('username');
            let preferences = [];

            if (currentUser) {
                try {
                    const res = await fetch(`http://localhost:3000/api/user-info?username=${currentUser}&t=${new Date().getTime()}`);
                    if (res.ok) {
                        const data = await res.json();
                        preferences = data.user && data.user.preferences ? data.user.preferences : [];
                        if (!Array.isArray(preferences)) preferences = [];
                    }
                } catch (e) {
                    console.error("获取偏好失败:", e);
                }
            }

            // 更新全局变量，供点击事件使用
            userPreferences = preferences;

            // 根据获取到的偏好更新提示内容
            if (preferences.length > 0) {
                tooltipContent.innerHTML = `
                    <i class="fas fa-info-circle me-2"></i>
                    根据您的偏好设置：${preferences.join(", ")}。如果需要更改偏好，请移动到个人中心。`;
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
        const MAX_SLICES = 19;

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
     * @function initializeOverviewModule
     * @description 初始化概述模块，包括为各种交互元素添加事件监听器并更新图表。
     */
    function initializeOverviewModule() {
        document.getElementById('yearlyInterval').addEventListener('change', function () {
            const isMonth = this.value === 'month';
            charts['yearly-trend'].setOption({
                xAxis: {data: isMonth ? Array.from({length: 12}, (_, i) => `${i + 1}月`) : ['春番', '夏番', '秋番', '冬番']},
                series: [{data: isMonth ? Array.from({length: 12}, () => Math.floor(Math.random() * 100 + 50)) : [200, 300, 250, 400]}]
            });
        });

        const preferenceChart = charts['preference-diff'];
        const preferenceSelect = document.getElementById('preferenceSelect');
        const animeButtonsContainer = document.getElementById('preference-anime-buttons');
        const userAnimes = ['咒术回战', '鬼灭之刃', '无职转生'];

        const updatePreferenceChart = () => {
            if (!charts['preference-diff']) return; // 安全检查
            const view = preferenceSelect.value;
            let data;
            if (view === 'region') data = [{name: '日本', value: 100}, {name: '中国', value: 50}, {
                name: '欧美',
                value: 30
            }];
            else if (view === 'age') data = [{name: '10-18岁', value: 80}, {
                name: '19-30岁',
                value: 120
            }, {name: '31-45岁', value: 40}, {name: '45-55岁', value: 20}, {name: '55岁以后', value: 10}];
            else data = [{name: '男', value: 150}, {name: '女', value: 90}];

            preferenceChart.setOption({series: [{data}]});
        };

        animeButtonsContainer.innerHTML = `<button class="btn btn-primary btn-sm active">所有番剧</button>` +
            userAnimes.map(name => `<button class="btn btn-outline-secondary btn-sm">${name}</button>`).join('');

        animeButtonsContainer.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON') {
                animeButtonsContainer.querySelectorAll('.btn').forEach(btn => {
                    btn.classList.remove('btn-primary', 'active');
                    btn.classList.add('btn-outline-secondary');
                });
                e.target.classList.add('btn-primary', 'active');
                e.target.classList.remove('btn-outline-secondary');
                updatePreferenceChart();
            }
        });

        preferenceSelect.addEventListener('change', updatePreferenceChart);

        document.getElementById('collectionInterval').addEventListener('change', () => {
            charts['collection-ratio'].setOption({
                series: [{data: Array.from({length: 5}, () => Math.floor(Math.random() * 200 + 20))}]
            });
        });

        const categoryTrendChart = charts['category-trend'];
        const categoryButtonsContainer = document.getElementById('category-trend-buttons');
        const categories = ['热血', '奇幻', '搞笑'];
        const categoryData = {
            '热血': [120, 132, 101, 134, 90, 230, 210],
            '奇幻': [220, 182, 191, 234, 290, 330, 310],
            '搞笑': [150, 232, 201, 154, 190, 330, 410]
        };

        const updateCategoryTrendChart = () => {
            if (!charts['category-trend']) return; // 安全检查
            const activeButtons = categoryButtonsContainer.querySelectorAll('.btn.active');
            const selectedCategories = Array.from(activeButtons).map(btn => btn.dataset.category);

            categoryTrendChart.setOption({
                legend: {
                    data: selectedCategories,
                    type: selectedCategories.length > 5 ? 'scroll' : 'plain'
                },
                series: selectedCategories.map(cat => ({
                    name: cat,
                    type: 'line',
                    smooth: true,
                    data: categoryData[cat]
                }))
            }, {
                notMerge: true
            });
        };

        categoryButtonsContainer.innerHTML = categories.map(cat =>
            `<button class="btn btn-primary btn-sm active" data-category="${cat}">${cat}</button>`
        ).join('');

        categoryButtonsContainer.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON') {
                e.target.classList.toggle('active');
                e.target.classList.toggle('btn-primary');
                e.target.classList.toggle('btn-outline-secondary');
                updateCategoryTrendChart();
            }
        });

        document.querySelectorAll('#overviewTabs button[data-bs-toggle="pill"]').forEach(tabEl => {
            tabEl.addEventListener('shown.bs.tab', event => {
                // 【修改】添加一个短暂的延时来确保 DOM 渲染完成
                setTimeout(() => {
                    const targetPane = document.querySelector(event.target.dataset.bsTarget);
                    if (!targetPane) return;

                    const chartEl = targetPane.querySelector('[id^="chart-"]');
                    if (chartEl) {
                        const chartIdKey = chartEl.id.replace('chart-', '');
                        if (charts[chartIdKey]) {
                            // 更新和重置尺寸现在都在延时后执行
                            if (chartIdKey === 'category-trend') {
                                updateCategoryTrendChart();
                            }
                            if (chartIdKey === 'preference-diff') {
                                updatePreferenceChart();
                            }
                            charts[chartIdKey].resize();
                        }
                    }
                }, 50); // 50毫秒的延时
            });
        });

        const activeTabPane = document.querySelector('#overviewTabsContent .tab-pane.active');
        if (activeTabPane && activeTabPane.querySelector('#chart-preference-diff')) {
            updatePreferenceChart();
        }
    }

    /**
     * @function initializeCharts
     * @description 初始化页面上所有的 ECharts 实例。
     * 该函数现在使用更清晰的结构和共享配置来创建图表。
     */
    function initializeCharts() {
        // --- 通用配置项 ---
        // 适用于大多数图表的通用网格边距设置
        const commonGrid = {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        };

        // 适用于大多数图表的通用提示框设置
        const commonTooltip = {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                label: {
                    backgroundColor: '#6a7985'
                }
            }
        };

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

        // 首页 - 季度趋势（折线图）
        const seasonTrendOption = {
            tooltip: commonTooltip,
            grid: commonGrid,
            xAxis: {type: "category", data: ["第一季度", "第二季度", "第三季度", "第四季度"]},
            yAxis: {type: "value"},
            series: [{
                name: '番剧数量',
                type: "line",
                smooth: true,
                data: [320, 432, 401, 534]
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
            grid: commonGrid,
            xAxis: {type: 'category', data: ['春番', '夏番', '秋番', '冬番']},
            yAxis: {type: 'value'},
            series: [{
                name: '上新数量',
                type: 'line',
                smooth: true,
                data: [200, 300, 250, 400] // 示例数据
            }]
        };

        // 番剧概览 - 用户偏好差异（矩形树图）
        const preferenceDiffOption = {
            tooltip: {trigger: 'item', formatter: "{b}: {c}"},
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

        // 番剧概览 - 追番评分占比（柱状图）
        const collectionRatioOption = {
            tooltip: commonTooltip,
            grid: commonGrid,
            xAxis: {type: 'category', data: ['9分以上', '8-9分', '7-8分', '6-7分', '6分以下']},
            yAxis: {type: 'value'},
            series: [{
                name: '番剧数量',
                type: 'bar',
                barWidth: '60%',
                data: [120, 200, 150, 80, 50] // 示例数据
            }]
        };

        // 番剧概览 - 类别热度趋势（折线图）
        const categoryTrendOption = {
            tooltip: commonTooltip,
            grid: {...commonGrid, bottom: '15%'}, // 为图例留出空间
            xAxis: {type: 'category', data: ["1月", "2月", "3月", "4月", "5月", "6月", "7月"]},
            yAxis: {type: 'value'},
            legend: {data: [], bottom: 0, type: 'scroll'},
            series: [] // 等待动态数据
        };

        // --- 批量执行初始化 ---
        initChart('chart-season-trend', seasonTrendOption);
        initChart('chart-play-trend', playTrendOption);
        initChart('chart-watch-time', watchTimeOption);
        initChart('chart-yearly-trend', yearlyTrendOption);
        initChart('chart-preference-diff', preferenceDiffOption);
        initChart('chart-collection-ratio', collectionRatioOption);
        initChart('chart-category-trend', categoryTrendOption);
    }
});