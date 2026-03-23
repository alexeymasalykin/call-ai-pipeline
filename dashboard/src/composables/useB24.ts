import { ref, shallowRef } from 'vue'
import { initializeB24Frame } from '@bitrix24/b24jssdk'

type B24Instance = Awaited<ReturnType<typeof initializeB24Frame>>

const instance = shallowRef<B24Instance | null>(null)
const initialized = ref(false)
const error = ref<string | null>(null)

export function useB24() {
  async function init(): Promise<void> {
    try {
      instance.value = await initializeB24Frame()
      initialized.value = true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Ошибка инициализации B24 SDK'
      throw e
    }
  }

  function getB24(): B24Instance {
    if (!instance.value) {
      throw new Error('B24Frame not initialized. Call init() first.')
    }
    return instance.value
  }

  return { init, getB24, initialized, error }
}
