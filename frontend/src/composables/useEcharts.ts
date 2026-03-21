// composables/useEcharts.ts
/**
 * 通用 ECharts 组合式函数
 *
 * 封装图表初始化、配置更新、加载状态及自动自适应逻辑：
 * - 使用 ResizeObserver 监听容器尺寸变化，自动调用 chart.resize()
 * - 在组件卸载时自动断开观察器并销毁图表实例，防止内存泄漏
 *
 * 使用方式：
 * ```ts
 * const { chartRef, initChart, setOption } = useEcharts()
 * // 模板中：<div ref="chartRef" style="height:400px"></div>
 * // 挂载后：initChart(option)
 * ```
 */
import { ref, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

export function useEcharts() {
  /** 绑定到图表容器 DOM 元素的模板 ref */
  const chartRef = ref<HTMLElement | null>(null)
  /** ECharts 实例（使用 shallowRef 避免深度响应式代理影响性能） */
  const chartInstance = shallowRef<echarts.ECharts | null>(null)
  /** 用于自适应容器尺寸的 ResizeObserver */
  let resizeObserver: ResizeObserver | null = null

  /**
   * 初始化图表并应用初始配置项。
   * 若容器元素已有旧实例，先销毁再重新初始化。
   *
   * @param option - 初始 ECharts 配置项
   */
  const initChart = (option: EChartsOption) => {
    if (!chartRef.value) return

    // 销毁旧实例，防止重复初始化
    if (chartInstance.value) {
      chartInstance.value.dispose()
    }

    chartInstance.value = echarts.init(chartRef.value)
    chartInstance.value.setOption(option)

    // 绑定 ResizeObserver，容器尺寸变化时自动调整图表大小
    resizeObserver = new ResizeObserver(() => {
      chartInstance.value?.resize()
    })
    resizeObserver.observe(chartRef.value)
  }

  /**
   * 更新图表配置项。
   *
   * @param option - 新的 ECharts 配置项
   * @param opts   - 可选的 setOption 参数（如 `{ notMerge: true }` 或 `{ replaceMerge: ['legend'] }`）
   */
  const setOption = (option: EChartsOption, opts?: object) => {
    chartInstance.value?.setOption(option, opts)
  }

  /** 显示加载动画 */
  const showLoading = () => chartInstance.value?.showLoading()

  /** 隐藏加载动画 */
  const hideLoading = () => chartInstance.value?.hideLoading()

  // 组件卸载时清理所有资源，防止内存泄漏
  onUnmounted(() => {
    if (resizeObserver && chartRef.value) {
      resizeObserver.unobserve(chartRef.value)
      resizeObserver.disconnect()
    }
    chartInstance.value?.dispose()
  })

  return {
    chartRef,
    chartInstance,
    initChart,
    setOption,
    showLoading,
    hideLoading,
  }
}
