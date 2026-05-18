<script setup lang="ts">
type IssueType = 'typo' | 'spelling' | 'agreement' | 'grammar'
type SegmentKind = 'plain' | 'replace' | 'underline'

interface SlideText {
  index: number
  text: string
}

interface Issue {
  slide: number
  fragment: string
  issue_type: IssueType
  message: string
  suggestion: string | null
  source: string
  start: number | null
  end: number | null
}

interface CheckResponse {
  filename?: string
  slides_count?: number
  slides?: SlideText[]
  issues?: Issue[]
  report?: string
  txt_url?: string
}

interface MarkSegment {
  kind: SegmentKind
  text: string
  suggestion?: string | null
  issue?: Issue
}

const selectedFile = ref<File | null>(null)
const result = ref<CheckResponse | null>(null)
const pending = ref(false)
const errorMessage = ref('')
const useLlm = ref(false)

const issueLabels: Record<IssueType, string> = {
  typo: 'Опечатка',
  spelling: 'Орфография',
  agreement: 'Согласование',
  grammar: 'Грамматика'
}

const issueColors: Record<IssueType, string> = {
  typo: 'warning',
  spelling: 'error',
  agreement: 'secondary',
  grammar: 'primary'
}

const resultIssues = computed(() => result.value?.issues ?? [])
const resultSlides = computed(() => result.value?.slides ?? [])
const resultFilename = computed(() => result.value?.filename ?? selectedFile.value?.name ?? 'presentation.pptx')
const resultSlidesCount = computed(() => result.value?.slides_count ?? resultSlides.value.length)

const slideRows = computed(() => {
  if (!result.value) {
    return []
  }

  return resultSlides.value.map((slide) => {
    const issues = resultIssues.value.filter((issue) => issue.slide === slide.index)
    return {
      ...slide,
      issues,
      segments: createSegments(slide.text, issues)
    }
  })
})

const reportText = computed(() => {
  if (!result.value) {
    return ''
  }

  if (result.value.report) {
    return result.value.report
  }

  if (resultIssues.value.length === 0) {
    return `Файл: ${resultFilename.value}\nСлайдов: ${resultSlidesCount.value}\nОшибки не найдены.`
  }

  return resultIssues.value
    .map((issue) => {
      const suggestion = issue.suggestion ? ` Возможно: "${issue.suggestion}".` : ''
      return `[Слайд ${issue.slide}] ${issue.fragment} -> ${issue.message}${suggestion}`
    })
    .join('\n')
})

function createSegments(text: string, issues: Issue[]): MarkSegment[] {
  const normalizedIssues = issues
    .map((issue) => {
      if (issue.start !== null && issue.end !== null) {
        return issue
      }

      const fallbackStart = text.indexOf(issue.fragment)
      return fallbackStart >= 0
        ? { ...issue, start: fallbackStart, end: fallbackStart + issue.fragment.length }
        : issue
    })
    .filter((issue) => issue.start !== null && issue.end !== null && issue.end > issue.start)
    .sort((a, b) => Number(a.start) - Number(b.start))

  const segments: MarkSegment[] = []
  let cursor = 0

  for (const issue of normalizedIssues) {
    const start = Number(issue.start)
    const end = Number(issue.end)
    if (start < cursor) {
      continue
    }

    if (start > cursor) {
      segments.push({ kind: 'plain', text: text.slice(cursor, start) })
    }

    const isReplacement = issue.issue_type === 'typo' || issue.issue_type === 'spelling'
    segments.push({
      kind: isReplacement ? 'replace' : 'underline',
      text: text.slice(start, end),
      suggestion: issue.suggestion,
      issue
    })
    cursor = end
  }

  if (cursor < text.length) {
    segments.push({ kind: 'plain', text: text.slice(cursor) })
  }

  return segments.length ? segments : [{ kind: 'plain', text }]
}

async function runCheck() {
  if (!selectedFile.value) {
    errorMessage.value = 'Выберите pptx-файл.'
    return
  }

  if (!selectedFile.value.name.toLowerCase().endsWith('.pptx')) {
    errorMessage.value = 'MVP принимает только файлы .pptx.'
    return
  }

  pending.value = true
  errorMessage.value = ''
  result.value = null

  const form = new FormData()
  form.append('file', selectedFile.value)
  form.append('use_llm', String(useLlm.value))

  try {
    result.value = await $fetch<CheckResponse>('/api/check-pptx', {
      method: 'POST',
      body: form
    })
  } catch (error) {
    const fallback = 'Не удалось проверить файл.'
    if (typeof error === 'object' && error && 'data' in error) {
      const typedError = error as {
        data?: { detail?: string; statusMessage?: string; message?: string }
        message?: string
        status?: number
        statusCode?: number
        statusMessage?: string
      }
      const data = typedError.data
      const status = typedError.status || typedError.statusCode
      const message = data?.detail || data?.statusMessage || data?.message || typedError.statusMessage || typedError.message
      errorMessage.value = message ? `${fallback} ${message}` : status ? `${fallback} Код: ${status}.` : fallback
    } else {
      errorMessage.value = fallback
    }
  } finally {
    pending.value = false
  }
}

function downloadReport() {
  if (!reportText.value && !result.value?.txt_url) {
    return
  }

  const link = document.createElement('a')
  const baseName = resultFilename.value.replace(/\.pptx$/i, '') || 'report'

  if (result.value?.txt_url) {
    link.href = result.value.txt_url
    link.download = `${baseName}-proofread-report.txt`
    link.click()
    return
  }

  const blob = new Blob([reportText.value], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  link.href = url
  link.download = `${baseName}-proofread-report.txt`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <main class="min-h-screen bg-[#f6f7f9] text-slate-900">
    <div class="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <header class="border-b border-slate-200 pb-5">
        <h1 class="text-3xl font-semibold tracking-normal text-slate-950">PPTX Fixer</h1>
      </header>

      <section class="grid gap-6 lg:grid-cols-[360px_1fr]">
        <v-card class="rounded-lg border border-slate-200">
          <v-card-title class="text-lg font-semibold">Файл</v-card-title>
          <v-card-text class="flex flex-col gap-4">
            <v-file-input
              v-model="selectedFile"
              accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
              clearable
              label="Выберите .pptx"
              prepend-icon="mdi-file-powerpoint-outline"
              variant="outlined"
              density="comfortable"
              rounded="lg"
              :disabled="pending"
            />

            <v-switch
              v-model="useLlm"
              color="secondary"
              density="comfortable"
              hide-details
              inset
              label="Ollama"
              :disabled="pending"
            />

            <v-btn
              color="primary"
              prepend-icon="mdi-play-circle-outline"
              rounded="lg"
              :loading="pending"
              :disabled="pending || !selectedFile"
              block
              @click="runCheck"
            >
              Проверить
            </v-btn>

            <v-alert
              v-if="errorMessage"
              class="rounded-lg"
              type="error"
              variant="tonal"
              density="comfortable"
              :text="errorMessage"
            />
          </v-card-text>
        </v-card>

        <div class="flex min-h-[520px] flex-col gap-4">
          <v-card class="rounded-lg border border-slate-200">
            <v-card-title class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
              <span class="text-lg font-semibold">Результат</span>
              <v-btn
                v-if="result"
                class="sm:ml-8"
                color="secondary"
                variant="tonal"
                prepend-icon="mdi-download-outline"
                rounded="lg"
                @click="downloadReport"
              >
                Скачать TXT
              </v-btn>
            </v-card-title>
            <v-card-text>
              <div
                v-if="!result && !pending"
                class="flex min-h-[360px] items-center justify-center rounded-lg text-center text-slate-500"
              >
                Загрузите презентацию, чтобы получить отчет по слайдам.
              </div>

              <div
                v-else-if="pending"
                class="flex min-h-[360px] flex-col items-center justify-center gap-4 rounded-lg text-slate-600"
              >
                <v-progress-circular indeterminate color="primary" size="42" />
                <span>Идет локальная обработка файла</span>
              </div>

              <div v-else-if="result" class="flex flex-col gap-4">
                <div class="grid gap-3 sm:grid-cols-3">
                  <div class="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                    <div class="text-sm text-slate-500">Файл</div>
                    <div class="mt-1 truncate font-medium">{{ resultFilename }}</div>
                  </div>
                  <div class="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                    <div class="text-sm text-slate-500">Слайдов</div>
                    <div class="mt-1 font-medium">{{ resultSlidesCount }}</div>
                  </div>
                  <div class="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                    <div class="text-sm text-slate-500">Замечаний</div>
                    <div class="mt-1 font-medium">{{ resultIssues.length }}</div>
                  </div>
                </div>

                <v-alert
                  v-if="resultIssues.length === 0"
                  class="rounded-lg"
                  type="success"
                  variant="tonal"
                  density="comfortable"
                  text="Ошибки не найдены."
                />

                <div class="flex flex-col gap-4">
                  <section
                    v-for="slide in slideRows"
                    :key="slide.index"
                    class="overflow-hidden rounded-lg border border-slate-200 bg-white"
                  >
                    <div class="border-b border-slate-200 bg-slate-50 px-4 py-3 font-semibold">
                      Слайд {{ slide.index }}
                    </div>

                    <div class="flex flex-col gap-4 p-4">
                      <div class="rounded-lg border border-slate-200 bg-white p-4 text-base leading-8 text-slate-900">
                        <template v-if="slide.text">
                          <template
                            v-for="(segment, segmentIndex) in slide.segments"
                            :key="`${slide.index}-${segmentIndex}`"
                          >
                            <span v-if="segment.kind === 'plain'" class="whitespace-pre-wrap">{{ segment.text }}</span>
                            <span
                              v-else-if="segment.kind === 'replace'"
                              class="mx-0.5 inline-flex flex-wrap items-baseline gap-1 rounded-md bg-red-50 px-1.5 py-0.5"
                            >
                              <del class="font-medium text-red-700 decoration-2">{{ segment.text }}</del>
                              <span v-if="segment.suggestion" class="font-semibold text-emerald-700">
                                {{ segment.suggestion }}
                              </span>
                            </span>
                            <span
                              v-else
                              class="mx-0.5 rounded-md bg-amber-50 px-1.5 py-0.5 font-medium underline decoration-amber-500 decoration-2 underline-offset-4"
                            >
                              {{ segment.text }}
                            </span>
                            <span
                              v-if="segment.kind === 'underline' && segment.suggestion"
                              class="ml-1 text-sm font-semibold text-emerald-700"
                            >
                              {{ segment.suggestion }}
                            </span>
                          </template>
                        </template>
                        <span v-else class="text-slate-400">Текст на слайде не найден.</span>
                      </div>

                      <div v-if="slide.issues.length" class="divide-y divide-slate-100 rounded-lg border border-slate-200">
                        <article
                          v-for="issue in slide.issues"
                          :key="`${issue.slide}-${issue.fragment}-${issue.message}-${issue.suggestion}`"
                          class="grid gap-3 px-4 py-4 lg:grid-cols-[160px_1fr]"
                        >
                          <div>
                            <v-chip
                              :color="issueColors[issue.issue_type]"
                              variant="tonal"
                              size="small"
                              rounded="lg"
                            >
                              {{ issueLabels[issue.issue_type] }}
                            </v-chip>
                          </div>
                          <div class="min-w-0">
                            <div class="font-medium text-slate-950">{{ issue.fragment }}</div>
                            <div class="mt-1 text-sm text-slate-700">{{ issue.message }}</div>
                            <div v-if="issue.suggestion" class="mt-2 text-sm text-slate-600">
                              Возможно: <span class="font-medium text-slate-950">{{ issue.suggestion }}</span>
                            </div>
                            <div class="mt-2 text-xs uppercase tracking-normal text-slate-400">{{ issue.source }}</div>
                          </div>
                        </article>
                      </div>

                      <div v-else class="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                        Замечаний по слайду нет.
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            </v-card-text>
          </v-card>

          <v-card v-if="result" class="rounded-lg border border-slate-200">
            <v-card-title class="text-lg font-semibold">Текстовый отчет</v-card-title>
            <v-card-text>
              <pre class="max-h-[320px] overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-800">{{ reportText }}</pre>
            </v-card-text>
          </v-card>
        </div>
      </section>
    </div>
  </main>
</template>
