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

    // ------------------- 2. 全局变量、常量和状态管理 -------------------

    // 【优化】将 API 基础 URL 定义为常量
    const API_BASE_URL = 'http://localhost:5000';
    const AUTH_API_BASE_URL = 'http://localhost:3000';

    // 【优化】将常用的 DOM 元素缓存在常量中，提高性能并使代码更整洁。
    const elements = {
        preferencesBtn: document.getElementById('preferencesBtn'),
        rankListContainer: document.getElementById('rank-list-container'),
        sortButtons: document.getElementById('sortButtons'),
        typeDistributionControls: document.getElementById('type-distribution-controls'),
        chartLevelIndicator: document.getElementById('chart-level-indicator'),
        backToMainChartBtn: document.getElementById('back-to-main-chart'),
        keywordInput: document.getElementById('keyword-input'),
        searchBtn: document.getElementById('search-btn'),
        favoritesCount: document.getElementById('favorites-count'),
        viewsCount: document.getElementById('views-count'),
        statusMessage: document.getElementById('status-message'),
        collectionIntervalSelect: document.getElementById('collectionInterval'),
        preferenceAnimeButtons: document.getElementById('preference-anime-buttons'),
        yearlyControlButtons: document.getElementById('yearly-control-buttons'),
        ratingControlButtons: document.getElementById('rating-control-buttons'),
        comboDetailPanel: document.querySelector('#category .combo-detail-panel'),
        categoryChartContainer: document.querySelector('#category .chart-container'),
        userInfo: document.getElementById("userInfo"),
        logoutBtn: document.getElementById("logoutBtn"),
    };

    let charts = {};
    let currentAnimeData = null;

    // 用于饼图下钻的状态变量
    let isTypeChartDrilledDown = false;
    let typeChartTopLevelData = {};
    let typeChartOtherData = {};

    // 用于偏好推荐的状态变量
    let isPreferenceMode = false; // 偏好模式是否激活
    let userPreferences = []; // 存储从后端获取的用户偏好
    let currentSortBy = 'score'; // 当前的排序标准
    let selectedAreasForReputationChart = ['国内', '日本', '美国'];

    // ------------------- 【核心修改 1/3】: 新增一个通用的、带自动 resize 功能的图表初始化函数 -------------------
    /**
     * @function initChartWithResizeObserver
     * @description 初始化 ECharts 实例并使用 ResizeObserver 自动监听容器尺寸变化以调整图表大小。
     * @param {string} elementId - 图表容器的 DOM 元素 ID.
     * @param {object} option - ECharts 的配置项.
     * @returns {echarts.ECharts | null} - 返回 ECharts 实例或 null.
     */
    function initChartWithResizeObserver(elementId, option) {
        const element = document.getElementById(elementId);
        if (!element) {
            console.error(`图表容器 #${elementId} 未找到。`);
            return null;
        }

        // Check if echarts is loaded
        if (typeof echarts === 'undefined') {
            console.error('ECharts library is not loaded.');
            return null;
        }

        // 销毁可能存在的旧实例
        const existingInstance = echarts.getInstanceByDom(element);
        if (existingInstance) {
            existingInstance.dispose();
        }

        const chart = echarts.init(element);
        chart.setOption(option);

        // 使用 ResizeObserver 监听容器大小变化
        const resizeObserver = new ResizeObserver(() => {
            chart.resize();
        });
        resizeObserver.observe(element);

        // 将图表实例存入全局对象
        charts[elementId.replace('chart-', '')] = chart;
        return chart;
    }

    /**
     * @function fetchUserPreferences
     * @description 获取当前登录用户的偏好设置。
     */
    async function fetchUserPreferences() {
        const currentUser = localStorage.getItem('username') || sessionStorage.getItem('username');
        if (!currentUser) return;
        try {
            const res = await fetch(`${AUTH_API_BASE_URL}/api/user-info?username=${currentUser}&t=${new Date().getTime()}`);
            if (res.ok) {
                const data = await res.json();
                userPreferences = (data.user && Array.isArray(data.user.preferences)) ? data.user.preferences : [];
            } else {
                console.error("获取用户偏好失败:", res.status);
                userPreferences = [];
            }
        } catch (error) {
            console.error("获取用户偏好时发生网络错误:", error);
            userPreferences = [];
        }
    }

    // ------------------- 2.1 全局通用 ECharts 配置 -------------------
    const commonGrid = {left: '3%', right: '4%', bottom: '3%', containLabel: true};
    const commonTooltip = {
        trigger: 'axis', axisPointer: {type: 'cross', label: {backgroundColor: '#6a7985'}}
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

    /**
     * @function ensureElementVisible
     * @description 确保元素可见的辅助函数
     */
    function ensureElementVisible(selector) {
        return new Promise((resolve) => {
            const element = document.querySelector(selector);
            if (!element) {
                resolve(false);
                return;
            }
            const checkVisibility = () => {
                if (element.offsetParent !== null) resolve(true); else setTimeout(checkVisibility, 50);
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
            if (targetSection) targetSection.classList.remove("d-none");

            navLinks.forEach(navLink => {
                navLink.classList.remove("active");
                if (navLink.getAttribute("href") === `#${sectionId}`) navLink.classList.add("active");
            });
            // 【核心修改】: 这里的 resize 逻辑可以移除，因为 ResizeObserver 会自动处理。
            // 但如果切换 section 导致 flex 容器尺寸在JS切换后才最终确定，保留一个延时 resize 作为双重保险也可以。
            // 为了最稳妥的体验，我们在这里保留一个延时，但时间可以缩短。
            setTimeout(() => {
                const visibleChart = targetSection.querySelector('[id^="chart-"]');
                if (visibleChart && typeof echarts !== 'undefined') {
                    const chartInstance = echarts.getInstanceByDom(visibleChart);
                    if (chartInstance) chartInstance.resize();
                }
            }, 50);
        };

        navLinks.forEach(link => {
            link.addEventListener("click", function (e) {
                const href = this.getAttribute("href");
                // Only handle hash links (internal navigation), allow external links to work normally
                if (href && href.startsWith("#")) {
                    e.preventDefault();
                    showSection(href.substring(1));
                }
            });
        });

        backButtons.forEach(btn => btn.addEventListener("click", () => showSection("home")));
        elements.userInfo.addEventListener("click", () => window.location.href = 'personal-space.html');
        elements.logoutBtn.addEventListener("click", () => {
            localStorage.clear();
            sessionStorage.clear();
            window.location.href = 'login.html';
        });
    }

    /**
     * @function initializeHomepage
     * @description 初始化首页所有数据，包括总览卡片和排行榜。
     */
    async function initializeHomepage() {
        // --- 总览卡片数据加载逻辑 ---
        const fetchMonthlyData = async (month) => {
            if (month < 1) return null;
            try {
                const response = await fetch(`${API_BASE_URL}/api/monthly_data/${month}`);
                return response.ok ? await response.json() : null;
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

        const [currentData, previousData] = await Promise.all([fetchMonthlyData(currentMonth), fetchMonthlyData(previousMonth)]);

        if (currentData) {
            const previousRatio = previousData && previousData.total_views > 0 ? (previousData.total_favorites / previousData.total_views) * 100 : 0;
            const currentRatio = currentData.total_views > 0 ? (currentData.total_favorites / currentData.total_views) * 100 : 0;
            const summaryData = {
                total_anime: {
                    value: currentData.source_bangumi_count || 0,
                    growth: calculateGrowth(currentData.source_bangumi_count, previousData ? previousData.source_bangumi_count : 0)
                }, total_views: {
                    value: currentData.total_views || 0,
                    growth: calculateGrowth(currentData.total_views, previousData ? previousData.total_views : 0)
                }, total_favorites: {
                    value: currentData.total_favorites || 0,
                    growth: calculateGrowth(currentData.total_favorites, previousData ? previousData.total_favorites : 0)
                }, collection_ratio: {value: currentRatio, change: currentRatio - previousRatio}
            };
            updateHomepageCards(summaryData);
        } else {
            console.error("无法加载当前月份的核心数据。");
        }

        // --- 【核心修改】排行榜数据加载和排序逻辑 ---
        initializeRankListControls();
        await updateRankDisplay();
        await updateTypeDistributionChart();
        await updateReputationPopularityChart();

        document.getElementById('reputation-chart-controls').addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
                const area = e.target.value;
                if (e.target.checked) {
                    // 如果选中，添加到数组
                    if (!selectedAreasForReputationChart.includes(area)) {
                        selectedAreasForReputationChart.push(area);
                    }
                } else {
                    // 如果取消选中，从数组中移除
                    selectedAreasForReputationChart = selectedAreasForReputationChart.filter(a => a !== area);
                }
                // 重新获取并渲染图表
                updateReputationPopularityChart();
            }
        });
    }

    /**
     * @function initializePreferencesTooltip
     * @description 初始化偏好提示功能，包括为按钮添加悬停提示，并绑定点击事件。
     */
    function initializePreferencesTooltip() {
        if (!elements.preferencesBtn) return;
        const tooltip = document.createElement("div");
        tooltip.id = "preferencesTooltip";
        tooltip.className = "preferences-tooltip";
        tooltip.style.display = "none";

        const tooltipContent = document.createElement("div");
        tooltipContent.className = "tooltip-content";
        tooltip.appendChild(tooltipContent);
        elements.preferencesBtn.parentNode.appendChild(tooltip);

        elements.preferencesBtn.addEventListener("mouseenter", () => {
            tooltipContent.innerHTML = userPreferences.length > 0 ? `<i class="fas fa-info-circle me-2"></i>根据您的偏好：${userPreferences.join(", ")}。` : `<i class="fas fa-exclamation-triangle me-2"></i>您尚未设置偏好，显示全部推荐。`;
            tooltip.style.display = "block";
        });

        elements.preferencesBtn.addEventListener("mouseleave", () => {
            tooltip.style.display = "none";
        });
    }

    /**
     * @function updateRankDisplay
     * @description 【新增】从后端获取根据当前选项（排序、偏好）处理好的排名列表并渲染。
     */
    async function updateRankDisplay() {
        elements.rankListContainer.innerHTML = '<div class="d-flex justify-content-center align-items-center py-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
        try {
            const params = new URLSearchParams({
                sortBy: currentSortBy,
                isPreferenceMode: isPreferenceMode,
                preferences: isPreferenceMode ? userPreferences.join(',') : ''
            });
            const response = await fetch(`${API_BASE_URL}/api/rank_list?${params.toString()}`);
            const animesToDisplay = await response.json();
            renderRankList(animesToDisplay, currentSortBy);
        } catch (error) {
            console.error('获取排行榜数据失败:', error);
            elements.rankListContainer.innerHTML = '<div class="text-center py-5">加载失败，请刷新重试</div>';
        }
    }

    /**
     * @function initializeRankListControls
     * @description 【新增】初始化排行榜的控制按钮（排序按钮、偏好开关）。
     */
    function initializeRankListControls() {
        initializePreferencesTooltip();

        elements.sortButtons.addEventListener('click', (e) => {
            const button = e.target.closest('button');
            if (button && button.dataset.sort !== currentSortBy) {
                elements.sortButtons.querySelectorAll('.btn').forEach(btn => {
                    btn.classList.remove('btn-primary', 'active');
                    btn.classList.add('btn-outline-primary');
                });
                button.classList.add('btn-primary', 'active');
                button.classList.remove('btn-outline-primary');
                currentSortBy = button.dataset.sort;
                updateRankDisplay();
            }
        });

        elements.preferencesBtn.addEventListener('click', () => {
            isPreferenceMode = !isPreferenceMode;
            elements.preferencesBtn.classList.toggle('active', isPreferenceMode);
            updateRankDisplay();
        });
    }


    /**
     * @function updateTypeDistributionChart
     * @description 准备并渲染饼图数据，包括顶级视图和下钻视图。。
     */
    async function updateTypeDistributionChart() {
        const response = await fetch(`${API_BASE_URL}/api/type_distribution_chart`);
        const sortedStyles = await response.json();

        if (sortedStyles.length === 0) {
            typeChartTopLevelData = {seriesData: []};
            typeChartOtherData = {seriesData: []};
            renderTypeDistributionChart();
            return;
        }

        let topLevelSeriesData;
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
                typeChartOtherData = {seriesData: otherItems.map(([name, value]) => ({name, value}))};
            }
        }

        typeChartTopLevelData = {seriesData: topLevelSeriesData};
        isTypeChartDrilledDown = false;
        renderTypeDistributionChart();
    }

    /**
     * @function renderTypeDistributionChart
     * @description 根据当前状态渲染饼图，并始终保持左右图例布局。
     */
    function renderTypeDistributionChart() {
        const chart = charts['type-distribution'];
        const dataToShow = isTypeChartDrilledDown ? typeChartOtherData.seriesData : typeChartTopLevelData.seriesData;

        if (!dataToShow || dataToShow.length === 0) {
            chart.setOption({series: [{data: []}], legend: [{}, {}]});
            elements.typeDistributionControls.classList.add('d-none');
            return;
        }

        const legendNames = dataToShow.map(item => item.name);
        const midIndex = Math.ceil(legendNames.length / 2);
        const legendDataLeft = legendNames.slice(0, midIndex);
        const legendDataRight = legendNames.slice(midIndex);

        chart.setOption({
            legend: [{orient: 'vertical', left: '5%', top: 'center', data: legendDataLeft}, {
                orient: 'vertical',
                right: '5%',
                top: 'center',
                data: legendDataRight
            }], series: [{data: dataToShow}]
        }, {replaceMerge: ['legend']});

        if (isTypeChartDrilledDown) {
            elements.chartLevelIndicator.textContent = '已细分合并的部分';
            elements.typeDistributionControls.classList.remove('d-none');
            elements.typeDistributionControls.classList.add('d-flex');
        } else {
            elements.typeDistributionControls.classList.add('d-none');
            elements.typeDistributionControls.classList.remove('d-flex');
        }
    }

    /**
     * @function updateHomepageCards
     * @description 根据传入的数据更新首页的四个总览卡片。
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
     * @param {string} sortBy - 排序依据，用于决定显示哪个指标。
     */
    function renderRankList(animes, sortBy) {
        if (!Array.isArray(animes) || animes.length === 0) {
            elements.rankListContainer.innerHTML = `<div class="text-center py-5">${isPreferenceMode && userPreferences.length > 0 ? '没有找到符合您偏好的番剧' : '暂无数据'}</div>`;
            return;
        }
        const topAnimes = animes;

        const formatLargeNumber = (num) => {
            if (num >= 1e8) return (num / 1e8).toFixed(1) + '亿';
            if (num >= 1e4) return (num / 1e4).toFixed(1) + '万';
            return num.toLocaleString();
        };

        elements.rankListContainer.innerHTML = topAnimes.map((anime, index) => {
            const rankClass = index < 3 ? 'top3' : '';
            const proxyUrl = `${API_BASE_URL}/api/image_proxy?url=${encodeURIComponent(anime.cover)}&title=${encodeURIComponent(anime.title)}&season_id=${anime.season_id}`;

            let displayValue;
            let valueIconClass;
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

            const animeStyles = anime.styles || [];
            let tagsHtml;

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
     * @description 处理番剧数据并更新口碑热度分布散点图
     */
    async function updateReputationPopularityChart() {
        try {
            const areasQuery = selectedAreasForReputationChart.join(',');
            const response = await fetch(`${API_BASE_URL}/api/reputation_popularity_chart?areas=${encodeURIComponent(areasQuery)}`);
            const chartData = await response.json();
            const areaColorMap = {
                '国内': '#FB7299', // 粉色
                '日本': '#23ADE5', // 蓝色
                '美国': '#FFCE56', // 黄色
            };

            const seriesData = chartData.map(item => ({
                value: item, itemStyle: {
                    color: areaColorMap[item[5]] || '#cccccc' // item[5] 是地区信息
                }
            }));

            const fullOption = {
                tooltip: {
                    trigger: 'item', formatter: function (params) {
                        if (params.value) {
                            const [jitteredScore, followers, title, views, originalScore, area] = params.value;
                            const scoreToDisplay = originalScore !== undefined ? originalScore : jitteredScore;
                            const formattedFollowers = followers >= 10000 ? (followers / 10000).toFixed(1) + '万' : followers;
                            const formattedViews = views >= 10000 ? (views / 10000).toFixed(1) + '万' : views;
                            return `${params.marker}<b>${title}</b><br/>地区: <b>${area || '未知'}</b><br/>评分: <b>${scoreToDisplay.toFixed(1)}</b><br/>追番: <b>${formattedFollowers}</b><br/>播放: <b>${formattedViews}</b>`;
                        }
                        return '无数据';
                    }
                }, grid: {left: '3%', right: '4%', bottom: '3%', containLabel: true}, xAxis: {
                    type: 'value', nameLocation: 'middle', nameGap: 25, splitLine: {lineStyle: {type: 'dashed'}}, min: 7
                }, yAxis: {
                    type: 'log', name: '追番人数', splitLine: {lineStyle: {type: 'dashed'}}, min: 1000
                }, series: [{
                    name: '番剧',
                    type: 'scatter',
                    symbolSize: 10,
                    data: seriesData,
                    emphasis: {focus: 'series', label: {show: true, formatter: (p) => p.value[2], position: 'top'}}
                }]
            };
            const chart = charts['season-trend'];
            if (chart) {
                chart.setOption(fullOption, true);
            }

        } catch (error) {
            console.error('更新口碑热度分布图表失败:', error);
        }
    }

    /**
     * @function initializeBangumiSearch
     * @description 初始化番剧状态检测模块，并添加图表联动功能。
     */
    function initializeBangumiSearch() {
        const formatNumber = (num) => {
            if (num === null || num === undefined) return '--';
            if (num < 1e4) return num.toString();
            if (num < 1e8) return (num / 1e4).toFixed(1) + '万';
            return (num / 1e8).toFixed(1) + '亿';
        };

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

        const findPeakTimeSlot = (onlineHistory) => {
            if (!onlineHistory || typeof onlineHistory !== 'object') return '暂无数据';
            const slots = {
                "00:00": '0-4点',
                "04:00": '4-8点',
                "08:00": '8-12点',
                "12:00": '12-16点',
                "16:00": '16-20点',
                "20:00": '20-24点'
            };
            let maxValue = 0;
            let peakSlot = '';
            for (const [time, count] of Object.entries(onlineHistory)) {
                if (count > maxValue) {
                    maxValue = count;
                    peakSlot = slots[time] || time;
                }
            }
            return peakSlot || '暂无数据';
        };

        const getPeakOnlineCount = (onlineHistory) => {
            if (!onlineHistory || typeof onlineHistory !== 'object') return 0;
            return Math.max(...Object.values(onlineHistory));
        };

        const updateEpisodeDetailsTable = (episodes) => {
            const detailsSection = document.getElementById('episode-details-section');
            const tbody = document.getElementById('episode-details-tbody');

            if (!episodes || episodes.length === 0) {
                detailsSection.style.display = 'none';
                return;
            }

            tbody.innerHTML = episodes.map((ep, index) => {
                const peakTime = findPeakTimeSlot(ep.online_history);
                const peakOnline = getPeakOnlineCount(ep.online_history);

                return `
                    <tr>
                        <td><span class="badge bg-primary">${index + 1}</span></td>
                        <td>${ep.title}</td>
                        <td>${formatNumber(ep.views || 0)}</td>
                        <td><span class="badge bg-info">${peakTime}</span></td>
                        <td>${formatNumber(peakOnline)}</td>
                    </tr>
                `;
            }).join('');

            detailsSection.style.display = 'block';
        };

        const performSearch = async () => {
            const keyword = elements.keywordInput.value.trim();
            if (!keyword) {
                elements.statusMessage.textContent = '请输入番剧名进行搜索。';
                return;
            }
            elements.searchBtn.disabled = true;
            elements.searchBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 搜索中...`;
            elements.statusMessage.textContent = `正在为"${keyword}"请求数据...`;
            elements.favoritesCount.textContent = '--';
            elements.viewsCount.textContent = '--';
            document.getElementById('episodes-count').textContent = '--';
            document.getElementById('avg-views').textContent = '--';
            document.getElementById('episode-details-section').style.display = 'none';

            try {
                const response = await fetch(`${API_BASE_URL}/search`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({keyword}),
                });
                const result = await response.json();
                if (!response.ok) {
                    elements.statusMessage.textContent = `错误: ${result.message}`;
                    elements.statusMessage.className = 'form-text mt-2 text-danger';
                    currentAnimeData = null;
                } else {
                    currentAnimeData = result.data;

                    // Update basic stats
                    elements.favoritesCount.textContent = formatNumber(currentAnimeData.stats.favorites);
                    elements.viewsCount.textContent = formatNumber(currentAnimeData.stats.views);

                    if (Array.isArray(currentAnimeData.episodes) && currentAnimeData.episodes.length > 0) {
                        const episodes = currentAnimeData.episodes;
                        const episodeCount = episodes.length;
                        const totalViews = episodes.reduce((sum, ep) => sum + (ep.views || 0), 0);
                        const avgViews = totalViews / episodeCount;

                        // Update enhanced stats
                        document.getElementById('episodes-count').textContent = episodeCount;
                        document.getElementById('avg-views').textContent = formatNumber(Math.round(avgViews));

                        // Update charts
                        const episodeLabels = episodes.map(ep => ep.title.replace(/第(\d+)话\s*/, '第$1话 '));
                        const episodeViews = episodes.map(ep => ep.views || 0);

                        charts['play-trend'].setOption({
                            xAxis: {data: episodeLabels, axisLabel: {interval: 0, rotate: 30}},
                            series: [{name: '单集播放量', data: episodeViews}]
                        });

                        // Update episode details table
                        updateEpisodeDetailsTable(episodes);
                    } else {
                        charts['play-trend'].setOption({xAxis: {data: []}, series: [{data: []}]});
                        document.getElementById('episodes-count').textContent = '0';
                        document.getElementById('avg-views').textContent = '0';
                    }

                    // 默认显示所有剧集的总和
                    const totalOnlineHistory = processOnlineHistory(currentAnimeData.episodes);
                    charts['watch-time'].setOption({
                        series: [{data: totalOnlineHistory}]
                    });
                    document.getElementById('watch-time-subtitle').textContent = '所有剧集总计';

                    elements.statusMessage.textContent = `成功获取数据。${result.status === 'cached' ? '(来自缓存)' : ''}`;
                    elements.statusMessage.className = 'form-text mt-2 text-success';
                }
            } catch (error) {
                elements.statusMessage.textContent = `错误: ${error.message}`;
                elements.statusMessage.className = 'form-text mt-2 text-danger';
                currentAnimeData = null;
            } finally {
                elements.searchBtn.disabled = false;
                elements.searchBtn.textContent = '搜索';
            }
        };

        elements.searchBtn.addEventListener('click', performSearch);
        elements.keywordInput.addEventListener('keyup', (event) => event.key === 'Enter' && performSearch());

        // Chart click interaction
        charts['play-trend'].on('click', (params) => {
            if (currentAnimeData && currentAnimeData.episodes && params.dataIndex >= 0) {
                const clickedEpisode = currentAnimeData.episodes[params.dataIndex];
                if (clickedEpisode) {
                    const singleEpisodeHistory = processOnlineHistory(clickedEpisode);
                    charts['watch-time'].setOption({
                        series: [{data: singleEpisodeHistory}]
                    });
                    document.getElementById('watch-time-subtitle').textContent = `${clickedEpisode.title}`;
                    elements.statusMessage.textContent = `当前显示《${clickedEpisode.title}》的在线人数分布。`;
                    elements.statusMessage.className = 'form-text mt-2 text-info';
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

        let buttonsHtml = '';
        if (containerId === "preference-anime-buttons") {
            const regions = ["国内", "日本", "美国", "其他"];
            buttonsHtml = regions.map((region, index) => {
                const isActive = index === 0;
                const buttonClass = isActive ? "btn btn-primary btn-sm active" : "btn btn-outline-secondary btn-sm";
                return `<button class="${buttonClass}" data-value="${region}">${region}</button>`;
            }).join("");
        } else {
            if (userPreferences.length === 0) {
                container.innerHTML = '<small class="text-muted">请先在个人中心设置偏好</small>';
                return;
            }
            buttonsHtml = `<button class="btn btn-primary btn-sm active" data-value="all">所有番剧</button>` + userPreferences.map(p => `<button class="btn btn-outline-secondary btn-sm" data-value="${p}">${p}</button>`).join("");
        }

        container.innerHTML = buttonsHtml;
        container.addEventListener("click", (e) => {
            if (e.target.tagName === "BUTTON") {
                container.querySelectorAll(".btn").forEach(btn => {
                    btn.classList.remove("btn-primary", "active");
                    btn.classList.add("btn-outline-secondary");
                });
                e.target.classList.add("btn-primary", "active");
                e.target.classList.remove("btn-outline-secondary");
                updateChartBasedOnSelection(containerId);
            }
        });
    }

    /**
     * @function updateChartBasedOnSelection
     * @description 根据选择更新图表
     */
    function updateChartBasedOnSelection(containerId) {
        // 这里需要根据具体的标签页实现不同的更新逻辑
        if (containerId === "preference-anime-buttons") {
            updatePreferenceChart();
        } else if (containerId === "yearly-control-buttons") {
            updateYearlyChart();
        } else if (containerId === "rating-control-buttons") {
            updateQualityScoreChart();
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

        trigger.addEventListener('click', () => customSelect.classList.toggle('open'));

        // 点击选项
        options.forEach(option => {
            option.addEventListener('click', () => {
                // 移除旧的选中状态
                options.forEach(opt => opt.classList.remove('selected'));
                // 添加新的选中状态
                option.classList.add('selected');
                // 更新显示文本
                trigger.querySelector('span').textContent = option.textContent;
                elements.collectionIntervalSelect.value = option.dataset.value;
                elements.collectionIntervalSelect.dispatchEvent(new Event('change'));
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
     * @description 更新偏好差异图表。
     */
    async function updatePreferenceChart() {
        const chart = charts['preference-diff'];
        try {
            chart.showLoading();
            const selectedButton = elements.preferenceAnimeButtons.querySelector('.btn.active');
            const selectedRegion = selectedButton ? selectedButton.dataset.value : '国内';
            const response = await fetch(`${API_BASE_URL}/api/preference_difference_chart?region=${selectedRegion}`);
            const chartData = await response.json();

            chart.setOption({
                tooltip: {
                    trigger: 'item', formatter: (params) => {
                        if ((params.data?.children && params.data.children.length > 0) || params.data?.value == null) {
                            return null;
                        }
                        const data = params.data;
                        let comparisonText = data.value > 1.1 ? `<span style="color: #28a745;">(高于全球)</span>` : data.value < 0.9 ? `<span style="color: #dc3545;">(低于全球)</span>` : `<span>(与全球持平)</span>`;
                        return `<b>${data.name}</b><br/>地区偏好指数: <b style="font-size: 1.2em;">${data.value}</b> ${comparisonText}<br/><hr style="margin: 4px 0;">该地区均追番: ${parseInt(data.regionalAvg).toLocaleString()}<br/>全球平均追番: ${parseInt(data.globalAvg).toLocaleString()}`;
                    }
                }, series: [{
                    type: 'treemap', roam: false, nodeClick: false, breadcrumb: {show: false}, label: {
                        show: true,
                        position: 'inside',
                        formatter: (p) => `${p.name}\n${p.value}`,
                        color: '#fff',
                        fontSize: 14
                    }, data: chartData.map(d => ({
                        ...d, itemStyle: {
                            color: userPreferences.includes(d.name) ? '#fb7299' : '#87CEFA',
                            borderRadius: 4,
                            borderWidth: 2,
                            borderColor: '#fff',
                            gapWidth: 2
                        }
                    }))
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
        const selectedButton = elements.yearlyControlButtons.querySelector('.btn.active');
        const selectedCategory = selectedButton ? selectedButton.dataset.value : 'all';

        try {
            chart.showLoading();
            const response = await fetch(`${API_BASE_URL}/api/yearly_quantity_chart?category=${selectedCategory}`);
            const yearlyData = await response.json();
            const legendData = Object.keys(yearlyData).sort((a, b) => b - a);
            const seriesData = legendData.map(year => ({
                name: year, type: 'line', smooth: true, data: yearlyData[year]
            }));

            const xData = ['春季(1-3月)', '夏季(4-6月)', '秋季(7-9月)', '冬季(10-12月)'];

            chart.setOption({
                tooltip: commonTooltip,
                xAxis: {data: xData},
                yAxis: {type: 'value', name: '番剧数量'},
                legend: {data: legendData},
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
        const chart = charts['collection-ratio'];
        chart.showLoading();
        const selectedButton = elements.ratingControlButtons.querySelector('.btn.active');
        const selectedCategory = selectedButton ? selectedButton.dataset.value : 'all';
        const selectedSeason = elements.collectionIntervalSelect.value;
        try {
            const response = await fetch(`${API_BASE_URL}/api/reputation_heat_index_chart?season=${selectedSeason}&category=${selectedCategory}`);
            const topAnimes = await response.json();
            const yAxisData = topAnimes.map(anime => anime.title).reverse();
            const seriesData = topAnimes.map(anime => ({
                value: parseFloat(anime.qualityScore.toFixed(0)),
                score: anime.score,
                views: anime.views,
                favorites: anime.favorites
            })).reverse();

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
                        return `<b>${params[0].name}</b><br/><span style="font-size:1.2em; color:#fde047; font-weight:bold;">口碑热度指数: ${formatNumber(data.value)}</span><br/><hr style="margin: 4px 0; border-color: rgba(255, 255, 255, 0.2);">B站评分: ${data.score}<br/>追番数: ${formatNumber(data.favorites)}<br/>播放量: ${formatNumber(data.views)}`;
                    }
                },
                grid: {...commonGrid, left: '5%', right: '10%'},
                xAxis: {type: 'value', name: '口碑热度指数'},
                yAxis: {
                    type: 'category',
                    data: yAxisData,
                    axisLabel: {show: false},
                    axisTick: {show: false},
                    axisLine: {show: false}
                },
                series: [{
                    name: '口碑热度指数', type: 'bar', barWidth: '60%', data: seriesData, itemStyle: {
                        borderRadius: [0, 5, 5, 0], color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{
                            offset: 0, color: '#f97316'
                        }, {offset: 1, color: '#facc15'}])
                    }, emphasis: {
                        itemStyle: {
                            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{
                                offset: 0, color: '#fb923c'
                            }, {offset: 1, color: '#fde047'}])
                        }
                    }
                }]
            };
            chart.setOption(fullOption, {notMerge: true});
        } catch (error) {
            console.error(error);
        } finally {
            chart.hideLoading();
        }
    }

    /**
     * @function updateStyleCombinationChart
     * @description 分析并更新“热门风格组合”图表。
     */
    async function updateStyleCombinationChart() {
        const chart = charts['category-trend'];
        chart.off('click');

        chart.showLoading();
        try {
            const response = await fetch(`${API_BASE_URL}/api/popular_style_combination_chart`);
            const topCombinations = await response.json();
            const seriesData = topCombinations.map(combo => ({
                name: combo.name, value: Math.round(combo.avgFavorites), count: combo.count, animes: combo.animes
            }));

            const fullOption = {
                tooltip: {
                    trigger: 'item',
                    backgroundColor: 'rgba(30, 41, 59, 0.9)',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    textStyle: {color: '#f0f0f0'},
                    formatter: function (params) {
                        if ((params.data.children && params.data.children.length > 0) || params.data.value == null) {
                            return null;
                        }
                        const {name, value, count, animes} = params.data;
                        const formatNumber = (num) => num ? num.toLocaleString() : 'N/A';
                        let animeListHtml = '';
                        if (animes && animes.length > 0) {
                            const displayAnimes = animes.slice(0, 5);
                            animeListHtml = displayAnimes.map(anime => `<li>${anime.title || '未知标题'}</li>`).join('');
                            if (animes.length > 5) animeListHtml += `<li>等 ${animes.length} 部番剧...</li>`;
                            animeListHtml = `<hr style="margin: 4px 0; border-color: rgba(255, 255, 255, 0.2);"><span style="color:#d1d5db;">包含番剧 (部分):</span><ul style="padding-left: 15px; margin-top: 5px; margin-bottom: 0;">${animeListHtml}</ul>`;
                        }
                        return `<b>${name}</b><br/><span style="font-size:1.2em; color:#34d399; font-weight:bold;">平均追番: ${formatNumber(value)}</span><br/><hr style="margin: 4px 0; border-color: rgba(255, 255, 255, 0.2);">包含番剧数: ${count}${animeListHtml}`;
                    }
                }, series: [{
                    type: 'treemap', roam: false, nodeClick: false, breadcrumb: {show: false}, label: {
                        show: true,
                        position: 'inside',
                        formatter: '{b}',
                        color: '#fff',
                        fontSize: 14,
                        fontWeight: 'bold'
                    }, itemStyle: {gapWidth: 3, borderColor: '#fff', borderRadius: 5}, data: seriesData
                }]
            };
            chart.setOption(fullOption, {notMerge: true});

            const closeBtn = elements.comboDetailPanel.querySelector('.btn-close-detail');

            chart.on('click', (params) => {
                if (params.data?.animes) {
                    const {name, value, count, animes} = params.data;
                    chart.dispatchAction({type: 'hideTip'});
                    chart.setOption({series: [{silent: true}]});

                    const detailBlock = document.getElementById('detail-block');
                    const detailBlockTitle = document.getElementById('detail-block-title');
                    detailBlock.style.backgroundColor = params.color;
                    detailBlockTitle.textContent = name;
                    elements.comboDetailPanel.querySelector('#detail-title').textContent = name;
                    elements.comboDetailPanel.querySelector('#detail-stats').textContent = `共 ${count} 部番剧 · 平均追番 ${value.toLocaleString()}`;

                    const animeListContainer = elements.comboDetailPanel.querySelector('.detail-anime-list');
                    const formatLargeNumber = (num) => {
                        if (num == null) return 'N/A';
                        if (num >= 1e8) return (num / 1e8).toFixed(1) + '亿';
                        if (num >= 1e4) return (num / 1e4).toFixed(1) + '万';
                        return num.toLocaleString();
                    };
                    animeListContainer.innerHTML = animes.map((anime, index) => {
                        const proxyUrl = `${API_BASE_URL}/api/image_proxy?url=${encodeURIComponent(anime.cover)}&title=${encodeURIComponent(anime.title)}&season_id=${anime.season_id}`;
                        return `<div class="detail-anime-item"><span class="rank">${index + 1}</span><img src="${proxyUrl}" alt="${anime.title}" class="cover"><div class="info"><h5>${anime.title}</h5><p><i class="fas fa-star"></i> ${anime.score || '暂无评分'} · <i class="fas fa-heart"></i> ${formatLargeNumber(anime.favorites)}</p></div></div>`;
                    }).join('');
                    elements.categoryChartContainer.classList.add('detail-view-active');
                }
            });
            closeBtn.onclick = () => {
                elements.categoryChartContainer.classList.remove('detail-view-active');
                chart.setOption({series: [{silent: false}]});
            };
        } catch (error) {
            console.error(error);
        } finally {
            chart.hideLoading();
        }
    }

    /**
     * @function initializeOverviewModule
     * @description 初始化概述模块，并为标签页切换添加精准的 resize 逻辑。
     */
    function initializeOverviewModule() {
        elements.collectionIntervalSelect.addEventListener('change', updateQualityScoreChart);

        initCommonControlButtons("preference-anime-buttons");
        initCommonControlButtons("yearly-control-buttons");
        initCommonControlButtons("rating-control-buttons");

        setTimeout(() => {
            updateYearlyChart();
            updatePreferenceChart();
            updateQualityScoreChart();
            updateStyleCombinationChart();
        }, 500);

        document.querySelectorAll('#overviewTabs button[data-bs-toggle="pill"]').forEach(tabEl => {
            tabEl.addEventListener("shown.bs.tab", (event) => {
                // 获取新激活的标签页内容区的 ID
                const targetPaneId = event.target.getAttribute('data-bs-target');
                if (!targetPaneId) return;

                // 找到该内容区内的图表容器
                const chartElement = document.querySelector(`${targetPaneId} [id^="chart-"]`);
                if (chartElement && typeof echarts !== 'undefined') {
                    // 获取对应的 ECharts 实例并调用 resize
                    const chartInstance = echarts.getInstanceByDom(chartElement);
                    if (chartInstance) {
                        chartInstance.resize();
                    }
                }
            });
        });
    }

    /**
     * @function initializeCharts
     * @description 初始化页面上所有的 ECharts 实例。
     */
    function initializeCharts() {

        // 首页 - 类型分布（饼图）
        const typeDistributionOption = {
            tooltip: {
                trigger: "item", formatter: (params) => {
                    if (!params || params.value == null || params.name == null) return '';
                    const defaultFormat = `${params.marker}${params.name}: ${params.value} (${params.percent}%)`;
                    if (params.name === '其他') return `${defaultFormat}<br><small style="color: #999; margin-left: 18px;">点击可查看细分</small>`;
                    return defaultFormat;
                }
            },
            legend: [{orient: 'vertical', left: '5%', top: 'center', data: []}, {
                orient: 'vertical',
                right: '5%',
                top: 'center',
                data: []
            }],
            series: [{
                name: '类型分布',
                type: "pie",
                radius: ["35%", "60%"],
                center: ['50%', '50%'],
                avoidLabelOverlap: false,
                itemStyle: {borderRadius: 10, borderColor: '#fff', borderWidth: 2},
                label: {show: false, position: 'center'},
                emphasis: {label: {show: true, fontSize: '20', fontWeight: 'bold'}},
                labelLine: {show: false},
                data: []
            }]
        };

        const typeChart = initChartWithResizeObserver('chart-type-distribution', typeDistributionOption);
        if (typeChart) {
            typeChart.on('click', (params) => {
                if (!isTypeChartDrilledDown && params.name === '其他' && typeChartOtherData.seriesData.length > 0) {
                    typeChart.dispatchAction({type: 'hideTip'});
                    isTypeChartDrilledDown = true;
                    renderTypeDistributionChart();
                }
            });
            elements.backToMainChartBtn.addEventListener('click', () => {
                if (isTypeChartDrilledDown) {
                    isTypeChartDrilledDown = false;
                    renderTypeDistributionChart();
                }
            });
        }
        // 首页 - 口碑热度分布（散点图）
        const reputationPopularityOption = {
            grid: commonGrid, xAxis: {name: '评分'}, yAxis: {name: '追番人数'}
        };

        // 番剧状态检测 - 播放量趋势（面积图）
        const playTrendOption = {
            tooltip: commonTooltip,
            grid: commonGrid,
            xAxis: {type: "category", boundaryGap: false, axisLabel: {show: false}, data: []},
            yAxis: {type: "value", name: "单集播放量"},
            series: [{name: "单集播放量", type: "line", areaStyle: {}, smooth: true, data: []}]
        };

        // 番剧状态检测 - 观看时间分布（柱状图）
        const watchTimeOption = {
            tooltip: commonTooltip,
            grid: commonGrid,
            xAxis: {type: 'category', data: ['0-4点', '4-8点', '8-12点', '12-16点', '16-20点', '20-24点']},
            yAxis: {type: 'value', name: "总在线人数"},
            series: [{name: '观看分布', type: 'bar', barWidth: '60%', data: [0, 0, 0, 0, 0, 0]}]
        };

        // 番剧概览 - 年度上新趋势（折线图）
        const yearlyTrendOption = {
            tooltip: commonTooltip,
            grid: commonGrid,
            xAxis: {type: 'category', data: []},
            yAxis: {type: 'value', name: '上新数量'},
            legend: {data: [], bottom: 0, type: 'scroll'},
            series: []
        };

        // 番剧概览 - 用户偏好差异（矩形树图）
        const preferenceDiffOption = {
            tooltip: {trigger: 'item'}, series: [{
                type: 'treemap',
                roam: false,
                nodeClick: false,
                breadcrumb: {show: false},
                label: {show: true, position: 'inside', formatter: '{b}\n{c}'},
                itemStyle: {gapWidth: 2},
                data: []
            }]
        };

        // 番剧概览 - 口碑热度指数（水平条形图）
        const collectionRatioOption = {
            tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'}},
            grid: {...commonGrid, left: '25%', right: '10%'},
            xAxis: {type: 'value', name: '口碑热度指数'},
            yAxis: {type: 'category', data: [], axisLabel: {show: false}},
            series: [{name: '口碑热度指数', type: 'bar', data: []}]
        };

        // 番剧概览 - 热门风格组合（矩形树图）
        const categoryTrendOption = {
            tooltip: {trigger: 'item'}, series: [{type: 'treemap', data: []}]
        };

        // --- 批量执行初始化 ---
        initChartWithResizeObserver('chart-season-trend', reputationPopularityOption);
        initChartWithResizeObserver('chart-play-trend', playTrendOption);
        initChartWithResizeObserver('chart-watch-time', watchTimeOption);
        initChartWithResizeObserver('chart-yearly-trend', yearlyTrendOption);
        initChartWithResizeObserver('chart-preference-diff', preferenceDiffOption);
        initChartWithResizeObserver('chart-collection-ratio', collectionRatioOption);
        initChartWithResizeObserver('chart-category-trend', categoryTrendOption);
    }

    /**
     * @function initializeRecommendationSection
     * @description Initialize the new recommendation section
     */
    async function initializeRecommendationSection() {
        const preferencesBtn2 = document.getElementById('preferencesBtn2');
        const sortButtons2 = document.getElementById('sortButtons2');
        const recommendationGrid = document.getElementById('recommendationGrid');
        let isPreferenceMode2 = false;
        let currentSortBy2 = 'score';

        // Initialize tooltip
        const tooltip2 = document.getElementById('preferencesTooltip2');
        if (preferencesBtn2 && tooltip2) {
            preferencesBtn2.addEventListener('mouseenter', () => {
                tooltip2.innerHTML = userPreferences.length > 0 ? `<i class="fas fa-info-circle me-2"></i>根据您的偏好：${userPreferences.join(", ")}。` : `<i class="fas fa-exclamation-triangle me-2"></i>您尚未设置偏好，显示全部推荐。`;
                tooltip2.style.display = 'block';
            });

            preferencesBtn2.addEventListener('mouseleave', () => {
                tooltip2.style.display = 'none';
            });
        }

        // Preference button click
        if (preferencesBtn2) {
            preferencesBtn2.addEventListener('click', () => {
                isPreferenceMode2 = !isPreferenceMode2;
                preferencesBtn2.classList.toggle('active', isPreferenceMode2);
                updateRecommendationGrid(currentSortBy2, isPreferenceMode2);
            });
        }

        // Sort buttons click
        if (sortButtons2) {
            sortButtons2.addEventListener('click', (e) => {
                const button = e.target.closest('button');
                if (button && button.dataset.sort !== currentSortBy2) {
                    sortButtons2.querySelectorAll('.btn').forEach(btn => {
                        btn.classList.remove('btn-primary', 'active');
                        btn.classList.add('btn-outline-primary');
                    });
                    button.classList.add('btn-primary', 'active');
                    button.classList.remove('btn-outline-primary');
                    currentSortBy2 = button.dataset.sort;
                    updateRecommendationGrid(currentSortBy2, isPreferenceMode2);
                }
            });
        }

        /**
         * Update recommendation grid
         */
        async function updateRecommendationGrid(sortBy, preferenceMode) {
            if (!recommendationGrid) return;

            recommendationGrid.innerHTML = '<div class="d-flex justify-content-center align-items-center py-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';

            try {
                const params = new URLSearchParams({
                    sortBy: sortBy,
                    isPreferenceMode: preferenceMode,
                    preferences: preferenceMode ? userPreferences.join(',') : ''
                });
                const response = await fetch(`${API_BASE_URL}/api/rank_list?${params.toString()}`);
                const animes = await response.json();

                if (!Array.isArray(animes) || animes.length === 0) {
                    recommendationGrid.innerHTML = `<div class="text-center py-5" style="grid-column: 1 / -1;">${preferenceMode && userPreferences.length > 0 ? '没有找到符合您偏好的番剧' : '暂无数据'}</div>`;
                    return;
                }

                const formatLargeNumber = (num) => {
                    if (num >= 1e8) return (num / 1e8).toFixed(1) + '亿';
                    if (num >= 1e4) return (num / 1e4).toFixed(1) + '万';
                    return num.toLocaleString();
                };

                recommendationGrid.innerHTML = animes.map((anime, index) => {
                    const proxyUrl = `${API_BASE_URL}/api/image_proxy?url=${encodeURIComponent(anime.cover)}&title=${encodeURIComponent(anime.title)}&season_id=${anime.season_id}`;

                    let displayValue;
                    let icon;
                    switch (sortBy) {
                        case 'views':
                            icon = 'fa-play-circle';
                            displayValue = formatLargeNumber(anime.views || 0);
                            break;
                        case 'followers':
                            icon = 'fa-heart';
                            displayValue = formatLargeNumber(anime.favorites || 0);
                            break;
                        default:
                            icon = 'fa-star';
                            displayValue = `${parseFloat(anime.score || 0).toFixed(1)}分`;
                            break;
                    }

                    const animeStyles = anime.styles || [];
                    let tagsHtml;

                    if (preferenceMode && userPreferences.length > 0) {
                        const matchingTags = animeStyles.filter(style => userPreferences.includes(style));
                        const otherTags = animeStyles.filter(style => !userPreferences.includes(style));
                        const orderedTags = [...matchingTags, ...otherTags];

                        tagsHtml = orderedTags.slice(0, 3).map(tag => {
                            const badgeClass = matchingTags.includes(tag) ? 'badge bg-primary me-1' : 'badge bg-secondary me-1';
                            return `<span class="${badgeClass}">${tag}</span>`;
                        }).join('');
                    } else {
                        tagsHtml = animeStyles.slice(0, 3).map(tag => `<span class="badge bg-secondary me-1">${tag}</span>`).join('');
                    }

                    const rankBadge = index < 3 ? `<div class="recommendation-rank-badge">Top ${index + 1}</div>` : '';

                    return `
                        <div class="recommendation-card">
                            <div class="recommendation-card-image-wrapper">
                                ${rankBadge}
                                <img src="${proxyUrl}" alt="${anime.title}" class="recommendation-card-image">
                            </div>
                            <div class="recommendation-card-content">
                                <div class="recommendation-card-title">${anime.title}</div>
                                <div class="recommendation-card-stats">
                                    <span><i class="fas ${icon}"></i>${displayValue}</span>
                                </div>
                                <div class="recommendation-card-tags">${tagsHtml}</div>
                            </div>
                        </div>
                    `;
                }).join('');
            } catch (error) {
                console.error('获取推荐数据失败:', error);
                recommendationGrid.innerHTML = '<div class="text-center py-5" style="grid-column: 1 / -1;">加载失败，请刷新重试</div>';
            }
        }

        // Initial load
        await updateRecommendationGrid(currentSortBy2, isPreferenceMode2);
    }

    // Initialize recommendation section
    initializeRecommendationSection();
});