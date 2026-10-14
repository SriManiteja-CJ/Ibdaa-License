import { createContext, useCallback, useContext, useState } from 'react'

const ApplicationContext = createContext(null)

export const ApplicationProvider = ({ children }) => {
  const [applicant] = useState({
    email: 'abdullah.mohammed@gmail.com',
    mobile: '054 4411346',
    emiratesId: '784-1990-123456-7',
  })

  const [uploadedFiles, setUploadedFiles] = useState({
    screenshot: null,
    sitePlan: null,
    socialMediaUrl: '',
  })

  const [extraction, setExtraction] = useState(null) // raw extraction result from API

  const [formData, setFormData] = useState({
    tradeName: '',
    mainActivity: '',
    activitySections: [],
    socialMediaAccount: '',
    licenseMobileNumber: '',
    licenseEmail: '',
    location: '',
    address: '',
    latitude: '',
    longitude: '',
    makaniNumber: '',
    tradeNameArabic: '',
    activityArabic: '',
    socialMediaUrl: '',
    termsAccepted: false,
  })

  const [submissionResult, setSubmissionResult] = useState(null)

  const updateFormData = useCallback((fields) => {
    setFormData((prev) => ({ ...prev, ...fields }))
  }, [])

  const applyExtraction = (extractionData) => {
    setExtraction(extractionData)
    const mapping = {
      trade_name: 'tradeName',
      main_activity: 'mainActivity',
      activity_sections: 'activitySections',
      social_media_account: 'socialMediaAccount',
      license_mobile_number: 'licenseMobileNumber',
      license_email: 'licenseEmail',
      location: 'location',
      address: 'address',
      latitude: 'latitude',
      longitude: 'longitude',
      makani_number: 'makaniNumber',
      trade_name_arabic: 'tradeNameArabic',
      activity_arabic: 'activityArabic',
    }
    const updates = {}
    for (const [apiField, formField] of Object.entries(mapping)) {
      if (extractionData[apiField]?.value !== undefined) {
        updates[formField] = extractionData[apiField].value
      }
    }
    setFormData((prev) => ({ ...prev, ...updates }))
  }

  const getFieldStatus = (apiFieldName) => {
    if (!extraction) return 'idle'
    return extraction[apiFieldName]?.status || 'idle'
  }

  const getFieldConfidence = (apiFieldName) => {
    if (!extraction) return 0
    return extraction[apiFieldName]?.confidence || 0
  }

  return (
    <ApplicationContext.Provider
      value={{
        applicant,
        uploadedFiles,
        setUploadedFiles,
        extraction,
        formData,
        updateFormData,
        applyExtraction,
        getFieldStatus,
        getFieldConfidence,
        submissionResult,
        setSubmissionResult,
      }}
    >
      {children}
    </ApplicationContext.Provider>
  )
}

export const useApplication = () => {
  const ctx = useContext(ApplicationContext)
  if (!ctx) throw new Error('useApplication must be used within ApplicationProvider')
  return ctx
}
