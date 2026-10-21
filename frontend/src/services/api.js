import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

export const analyzeDocuments = async (screenshot, sitePlan, socialMediaUrl) => {
  const formData = new FormData()
  if (screenshot) formData.append('screenshot', screenshot)
  if (sitePlan) formData.append('site_plan', sitePlan)
  if (socialMediaUrl) formData.append('social_media_url', socialMediaUrl)
  const res = await api.post('/documents/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export const submitApplication = async (payload) => {
  const res = await api.post('/license/submit', payload)
  return res.data
}

export const getLLMProviders = async () => {
  const res = await api.get('/llm/providers')
  return res.data
}

export const checkLLMHealth = async () => {
  const res = await api.get('/llm/health')
  return res.data
}

export const getActivityCategories = async () => {
  const res = await api.get('/activity/categories')
  return res.data
}

export const suggestActivity = async (tradeName, tradeNameArabic = '', context = '') => {
  const res = await api.post('/activity/suggest', {
    trade_name: tradeName,
    trade_name_arabic: tradeNameArabic,
    context,
  })
  return res.data
}

export default api
