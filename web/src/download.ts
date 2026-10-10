export function downloadJson(data: unknown, filename: string) {
  downloadFile(JSON.stringify(data, null, 2), filename, 'application/json')
}

export function downloadFile(content: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a')
  link.href = url; link.download = filename; link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
