<template>
  <AudioRow
    v-for="(r, i) in rows"
    :key="r.id"
    v-model="rows[i]"
    :index="i"
    :readonly="readonly"
    @remove="remove"
    @toast="t => $emit('toast', t)"
  />
</template>

<script setup>
import AudioRow from './AudioRow.vue'

defineProps({
  rows: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  readonly: { type: Boolean, default: true }
})
const emit = defineEmits(['remove', 'toast'])

function remove(id) { emit('remove', id) }
</script>

