export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  srcDir: 'app/',
  ssr: false,
  modules: ['@nuxtjs/tailwindcss', 'vuetify-nuxt-module'],
  css: ['@mdi/font/css/materialdesignicons.css', '~/assets/css/tailwind.css'],
  typescript: {
    strict: true,
    typeCheck: true
  },
  runtimeConfig: {
    apiInternalBase: process.env.NUXT_API_INTERNAL_BASE || 'http://backend:8000'
  },
  vuetify: {
    vuetifyOptions: {
      icons: {
        defaultSet: 'mdi'
      },
      theme: {
        defaultTheme: 'proofreader',
        themes: {
          proofreader: {
            dark: false,
            colors: {
              primary: '#2457a6',
              secondary: '#2f7d6e',
              error: '#ba1a1a',
              warning: '#916400',
              success: '#277a3f',
              background: '#f6f7f9',
              surface: '#ffffff'
            }
          }
        }
      },
      defaults: {
        VBtn: {
          variant: 'flat'
        },
        VCard: {
          rounded: 'lg',
          elevation: 0
        }
      }
    }
  }
})
