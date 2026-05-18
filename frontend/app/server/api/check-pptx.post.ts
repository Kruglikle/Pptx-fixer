export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const parts = await readMultipartFormData(event)

  if (!parts?.length) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Файл не был передан.'
    })
  }

  const filePart = parts.find((part) => part.name === 'file')
  if (!filePart?.data) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Файл не был передан.'
    })
  }

  const form = new FormData()
  form.append(
    'file',
    new Blob([new Uint8Array(filePart.data)], {
      type: filePart.type || 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    }),
    filePart.filename || 'presentation.pptx'
  )

  for (const part of parts) {
    if (part.name && part.name !== 'file') {
      form.append(part.name, part.data.toString('utf8'))
    }
  }

  try {
    const response = await $fetch<Record<string, unknown>>(`${config.apiInternalBase}/api/check-pptx`, {
      method: 'POST',
      body: form
    })

    const report = typeof response.report === 'string' ? response.report : ''
    const filename = typeof response.filename === 'string' ? response.filename : filePart.filename || 'presentation.pptx'
    const slides = Array.isArray(response.slides)
      ? response.slides
      : report
        ? [{ index: 1, text: report }]
        : []

    return {
      ...response,
      filename,
      slides_count: typeof response.slides_count === 'number' ? response.slides_count : slides.length,
      slides,
      issues: Array.isArray(response.issues) ? response.issues : [],
      report,
      txt_url: typeof response.txt_url === 'string' ? response.txt_url : undefined
    }
  } catch (error) {
    const err = error as {
      data?: { detail?: string }
      status?: number
      statusCode?: number
      statusMessage?: string
      message?: string
    }
    throw createError({
      statusCode: err.statusCode || err.status || 502,
      statusMessage: err.data?.detail || err.statusMessage || err.message || 'Backend недоступен.'
    })
  }
})
