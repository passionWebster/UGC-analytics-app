// data-screen.js
document.addEventListener('DOMContentLoaded', async () => {
    // API Configuration
    const API_BASE_URL = 'http://localhost:5000';
    
    // Charts
    const charts = {};
    let currentRankType = 'score';
    
    // Initialize
    updateTime();
    setInterval(updateTime, 1000);
    
    initializeCharts();
    await loadData();
    initializeRankingTabs();
    
    // Auto refresh every 5 minutes
    setInterval(loadData, 5 * 60 * 1000);
    
    /**
     * Update current time display
     */
    function updateTime() {
        const now = new Date();
        const timeStr = now.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
        document.getElementById('currentTime').textContent = timeStr;
    }
    
    /**
     * Format large numbers
     */
    function formatNumber(num, unit = '') {
        if (num >= 1e8) return (num / 1e8).toFixed(1) + '亿' + unit;
        if (num >= 1e4) return (num / 1e4).toFixed(1) + '万' + unit;
        if (unit === '%') return num.toFixed(2) + unit;
        return num.toLocaleString() + unit;
    }
    
    /**
     * Load all data
     */
    async function loadData() {
        await Promise.all([
            loadMetrics(),
            loadTypeDistribution(),
            loadYearlyTrend(),
            loadTopRated(),
            loadRanking(currentRankType),
            loadStyleCombo()
        ]);
    }
    
    /**
     * Load metrics data
     */
    async function loadMetrics() {
        try {
            const today = new Date();
            const currentMonth = today.getMonth() + 1;
            const previousMonth = currentMonth === 1 ? 12 : currentMonth - 1;
            
            const [currentData, previousData] = await Promise.all([
                fetch(`${API_BASE_URL}/api/monthly_data/${currentMonth}`).then(r => r.json()),
                fetch(`${API_BASE_URL}/api/monthly_data/${previousMonth}`).then(r => r.json())
            ]);
            
            if (currentData) {
                const calculateGrowth = (current, previous) => {
                    if (!previous || previous === 0) return 0;
                    return ((current - previous) / previous) * 100;
                };
                
                // Total Anime
                const animeGrowth = calculateGrowth(
                    currentData.source_bangumi_count,
                    previousData?.source_bangumi_count
                );
                document.getElementById('totalAnime').textContent = formatNumber(currentData.source_bangumi_count);
                updateTrend('animeTrend', animeGrowth);
                
                // Total Views
                const viewsGrowth = calculateGrowth(
                    currentData.total_views,
                    previousData?.total_views
                );
                document.getElementById('totalViews').textContent = formatNumber(currentData.total_views);
                updateTrend('viewsTrend', viewsGrowth);
                
                // Total Followers
                const followersGrowth = calculateGrowth(
                    currentData.total_favorites,
                    previousData?.total_favorites
                );
                document.getElementById('totalFollowers').textContent = formatNumber(currentData.total_favorites);
                updateTrend('followersTrend', followersGrowth);
                
                // Average Rating (as collection ratio)
                const currentRatio = currentData.total_views > 0 
                    ? (currentData.total_favorites / currentData.total_views) * 100 
                    : 0;
                const previousRatio = previousData && previousData.total_views > 0
                    ? (previousData.total_favorites / previousData.total_views) * 100
                    : 0;
                document.getElementById('avgRating').textContent = formatNumber(currentRatio, '%');
                updateTrend('ratingTrend', currentRatio - previousRatio);
            }
        } catch (error) {
            console.error('Failed to load metrics:', error);
        }
    }
    
    /**
     * Update trend indicator
     */
    function updateTrend(elementId, value) {
        const element = document.getElementById(elementId);
        const isPositive = value >= 0;
        const icon = isPositive ? '↑' : '↓';
        const className = isPositive ? 'trend-up' : 'trend-down';
        element.innerHTML = `<span class="${className}">${icon} ${Math.abs(value).toFixed(1)}%</span>`;
    }
    
    /**
     * Load type distribution chart
     */
    async function loadTypeDistribution() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/type_distribution_chart`);
            const data = await response.json();
            
            const chartData = data.slice(0, 10).map(([name, value]) => ({
                name,
                value
            }));
            
            charts.typeDistribution.setOption({
                series: [{
                    data: chartData
                }]
            });
        } catch (error) {
            console.error('Failed to load type distribution:', error);
        }
    }
    
    /**
     * Load yearly trend chart
     */
    async function loadYearlyTrend() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/yearly_quantity_chart?category=all`);
            const yearlyData = await response.json();
            
            const years = Object.keys(yearlyData).sort((a, b) => b - a).slice(0, 5);
            const seasons = ['春季(1-3月)', '夏季(4-6月)', '秋季(7-9月)', '冬季(10-12月)'];
            
            const seriesData = years.map(year => ({
                name: year,
                type: 'line',
                smooth: true,
                data: yearlyData[year]
            }));
            
            charts.yearlyTrend.setOption({
                xAxis: { data: seasons },
                legend: { data: years },
                series: seriesData
            });
        } catch (error) {
            console.error('Failed to load yearly trend:', error);
        }
    }
    
    /**
     * Load top rated chart
     */
    async function loadTopRated() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/reputation_heat_index_chart?season=all&category=all`);
            const data = await response.json();
            
            const topAnimes = data.slice(0, 10);
            const yAxisData = topAnimes.map(anime => anime.title).reverse();
            const seriesData = topAnimes.map(anime => anime.qualityScore).reverse();
            
            charts.topRated.setOption({
                yAxis: { data: yAxisData },
                series: [{
                    data: seriesData
                }]
            });
        } catch (error) {
            console.error('Failed to load top rated:', error);
        }
    }
    
    /**
     * Load ranking list
     */
    async function loadRanking(sortBy) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/rank_list?sortBy=${sortBy}&isPreferenceMode=false`);
            const animes = await response.json();
            
            const container = document.getElementById('rankingList');
            container.innerHTML = animes.map((anime, index) => {
                const rankClass = index === 0 ? 'top1' : index === 1 ? 'top2' : index === 2 ? 'top3' : '';
                const proxyUrl = `${API_BASE_URL}/api/image_proxy?url=${encodeURIComponent(anime.cover)}&title=${encodeURIComponent(anime.title)}&season_id=${anime.season_id}`;
                
                let displayValue;
                let icon;
                switch (sortBy) {
                    case 'views':
                        icon = 'fa-play-circle';
                        displayValue = formatNumber(anime.views || 0);
                        break;
                    case 'followers':
                        icon = 'fa-heart';
                        displayValue = formatNumber(anime.favorites || 0);
                        break;
                    default:
                        icon = 'fa-star';
                        displayValue = `${parseFloat(anime.score || 0).toFixed(1)}分`;
                        break;
                }
                
                return `
                    <div class="ranking-item">
                        <div class="rank-number ${rankClass}">${index + 1}</div>
                        <img src="${proxyUrl}" alt="${anime.title}" class="rank-image">
                        <div class="rank-info">
                            <div class="rank-title">${anime.title}</div>
                            <div class="rank-stats">
                                <span><i class="fas ${icon}"></i> ${displayValue}</span>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        } catch (error) {
            console.error('Failed to load ranking:', error);
        }
    }
    
    /**
     * Load style combo chart
     */
    async function loadStyleCombo() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/popular_style_combination_chart`);
            const data = await response.json();
            
            const chartData = data.slice(0, 15).map(combo => ({
                name: combo.name,
                value: Math.round(combo.avgFavorites)
            }));
            
            charts.styleCombo.setOption({
                series: [{
                    data: chartData
                }]
            });
        } catch (error) {
            console.error('Failed to load style combo:', error);
        }
    }
    
    /**
     * Initialize ranking tabs
     */
    function initializeRankingTabs() {
        document.querySelectorAll('.rank-tab').forEach(tab => {
            tab.addEventListener('click', function() {
                document.querySelectorAll('.rank-tab').forEach(t => t.classList.remove('active'));
                this.classList.add('active');
                currentRankType = this.dataset.type;
                loadRanking(currentRankType);
            });
        });
    }
    
    /**
     * Initialize all charts
     */
    function initializeCharts() {
        // Type Distribution - Pie Chart
        charts.typeDistribution = echarts.init(document.getElementById('chartTypeDistribution'));
        charts.typeDistribution.setOption({
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                borderColor: '#fb7299',
                textStyle: { color: '#fff' }
            },
            legend: {
                orient: 'vertical',
                right: '5%',
                top: 'center',
                textStyle: { color: '#fff' }
            },
            series: [{
                name: '类型分布',
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['40%', '50%'],
                avoidLabelOverlap: true,
                itemStyle: {
                    borderRadius: 10,
                    borderColor: '#0a0e27',
                    borderWidth: 2
                },
                label: {
                    show: true,
                    position: 'outside',
                    color: '#fff',
                    formatter: '{b}: {c}'
                },
                emphasis: {
                    label: {
                        show: true,
                        fontSize: '16',
                        fontWeight: 'bold'
                    }
                },
                data: []
            }]
        });
        
        // Yearly Trend - Line Chart
        charts.yearlyTrend = echarts.init(document.getElementById('chartYearlyTrend'));
        charts.yearlyTrend.setOption({
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                borderColor: '#fb7299',
                textStyle: { color: '#fff' }
            },
            legend: {
                bottom: 0,
                textStyle: { color: '#fff' }
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '12%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                boundaryGap: false,
                axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.3)' } },
                axisLabel: { color: '#fff' },
                data: []
            },
            yAxis: {
                type: 'value',
                name: '番剧数量',
                nameTextStyle: { color: '#fff' },
                axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.3)' } },
                axisLabel: { color: '#fff' },
                splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } }
            },
            series: []
        });
        
        // Top Rated - Bar Chart
        charts.topRated = echarts.init(document.getElementById('chartTopRated'));
        charts.topRated.setOption({
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                borderColor: '#fb7299',
                textStyle: { color: '#fff' }
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                containLabel: true
            },
            xAxis: {
                type: 'value',
                axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.3)' } },
                axisLabel: { color: '#fff' },
                splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } }
            },
            yAxis: {
                type: 'category',
                axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.3)' } },
                axisLabel: { 
                    color: '#fff',
                    fontSize: 11
                },
                data: []
            },
            series: [{
                name: '口碑热度指数',
                type: 'bar',
                barWidth: '60%',
                itemStyle: {
                    borderRadius: [0, 5, 5, 0],
                    color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        { offset: 0, color: '#fb7299' },
                        { offset: 1, color: '#23ade5' }
                    ])
                },
                data: []
            }]
        });
        
        // Style Combo - Treemap
        charts.styleCombo = echarts.init(document.getElementById('chartStyleCombo'));
        charts.styleCombo.setOption({
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                borderColor: '#fb7299',
                textStyle: { color: '#fff' },
                formatter: (params) => {
                    return `<b>${params.name}</b><br/>平均追番: ${formatNumber(params.value)}`;
                }
            },
            series: [{
                type: 'treemap',
                roam: false,
                nodeClick: false,
                breadcrumb: { show: false },
                label: {
                    show: true,
                    position: 'inside',
                    formatter: '{b}',
                    color: '#fff',
                    fontSize: 12,
                    fontWeight: 'bold'
                },
                itemStyle: {
                    gapWidth: 2,
                    borderColor: '#0a0e27',
                    borderWidth: 2
                },
                data: []
            }]
        });
        
        // Auto resize charts on window resize
        window.addEventListener('resize', () => {
            Object.values(charts).forEach(chart => chart.resize());
        });
    }
});
