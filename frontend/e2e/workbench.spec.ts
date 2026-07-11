import { expect, test } from '@playwright/test'
import path from 'node:path'

test('uploads data and renders a grounded analysis report', async ({ page }) => {
  await page.goto('/')
  await page.locator('input[type="file"]').setInputFiles(path.resolve(process.cwd(), '../samples/sales_sample.csv'))
  await page.getByRole('button', { name: '上传并生成画像' }).click()
  await expect(page.getByText('12 行', { exact: true })).toBeVisible()

  const question = page.getByPlaceholder('例如：按地区统计销售额最高的前 10 个地区，并生成图表')
  await question.fill('Average sales by region and generate a chart')
  await page.getByRole('button', { name: '开始分析' }).click()
  await expect(page.locator('.timeline').getByText('分析任务已完成。')).toBeVisible({ timeout: 30_000 })

  await page.getByRole('button', { name: '报告' }).click()
  await expect(page.getByRole('heading', { name: '数据分析报告' })).toBeVisible()
  await expect(page.locator('.markdown-body').getByText('执行路径：DuckDB SQL', { exact: true })).toBeVisible()
})
