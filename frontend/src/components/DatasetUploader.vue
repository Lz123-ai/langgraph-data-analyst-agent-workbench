<template>
  <section class="panel uploader">
    <div class="panel-title">
      <FileSpreadsheet :size="18" />
      <span>数据集</span>
    </div>
    <label class="drop-zone" :class="{ active: selectedFile }">
      <Upload :size="28" />
      <input type="file" accept=".csv,.xlsx,.xls" @change="onFileChange" />
      <span>{{ selectedFile ? selectedFile.name : '选择 CSV 或 Excel 文件' }}</span>
    </label>
    <button class="primary-button" :disabled="!selectedFile || uploading" @click="submit">
      <UploadCloud :size="16" />
      <span>{{ uploading ? '上传中' : '上传并生成画像' }}</span>
    </button>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { FileSpreadsheet, Upload, UploadCloud } from '@lucide/vue'

defineProps<{ uploading: boolean }>()
const emit = defineEmits<{ upload: [file: File] }>()

const selectedFile = ref<File | null>(null)

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
}

function submit() {
  if (selectedFile.value) {
    emit('upload', selectedFile.value)
  }
}
</script>
