import { useState, useCallback, useEffect, lazy, Suspense } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, QrCode, RefreshCw, CheckCircle2, Building2 } from 'lucide-react'
import Layout from '../components/layout/Layout'
import HeroBanner from '../components/layout/HeroBanner'
import InputField from '../components/ui/InputField'
import ActivityChip from '../components/ui/ActivityChip'
import Stepper from '../components/ui/Stepper'
import { useApplication } from '../context/ApplicationContext'
import { suggestActivity, getActivityCategories } from '../services/api'

// Lazy-load Leaflet to avoid SSR issues
const MapView = lazy(() => import('../components/ui/MapView'))

const STEPS = ['Upload Documents', 'Review Details', 'Validate & Submit']

const AI_FIELD_MAP = {
  tradeName: 'trade_name',
  mainActivity: 'main_activity',
  socialMediaAccount: 'social_media_account',
  licenseMobileNumber: 'license_mobile_number',
  licenseEmail: 'license_email',
  location: 'location',
  address: 'address',
  makaniNumber: 'makani_number',
}

export default function ReviewForm() {
  const navigate = useNavigate()
  const { formData, updateFormData, getFieldStatus, extraction } = useApplication()
  const [categories, setCategories] = useState([])
  const [matchingLoading, setMatchingLoading] = useState(false)

  useEffect(() => {
    // If no extraction, go back to upload
    if (!extraction) navigate('/services/ibdaa-license')
  }, [extraction, navigate])

  useEffect(() => {
    getActivityCategories()
      .then((res) => {
        if (res?.categories) setCategories(res.categories)
      })
      .catch((err) => console.warn('Could not load categories:', err))
  }, [])

  const handleReMatchActivity = async () => {
    if (!formData.tradeName) return
    setMatchingLoading(true)
    try {
      const res = await suggestActivity(
        formData.tradeName,
        formData.tradeNameArabic,
        formData.mainActivity
      )
      if (res?.recommendation) {
        const rec = res.recommendation
        updateFormData({
          mainActivity: rec.matched_activity_en,
          activityArabic: rec.matched_activity_ar,
          activityCategory: rec.category_name_en,
          activityReason: rec.match_reason,
          activitySections: rec.available_activities || formData.activitySections,
        })
      }
    } catch (e) {
      console.error('Failed to suggest activity:', e)
    } finally {
      setMatchingLoading(false)
    }
  }

  const status = (formKey) => getFieldStatus(AI_FIELD_MAP[formKey] || formKey)

  const handleLocationResolved = useCallback((resolved) => {
    updateFormData({
      location: resolved.location,
      address: resolved.address,
    })
  }, [updateFormData])

  const handleRemoveChip = (index) => {
    const updated = formData.activitySections.filter((_, i) => i !== index)
    updateFormData({ activitySections: updated })
  }

  return (
    <Layout>
      <HeroBanner
        eyebrow="DED Smart Services - Service Catalogue"
        title="Ibdaa License"
      />

      <Stepper steps={STEPS} current={1} />

      {/* Info Card */}
      <div className="info-card">
        <div className="info-card-body">
          <div className="info-card-desc">
            <p>A license to encourage UAE nationals &amp; residents (in Umm Al Quwain) to conduct business from home and online (social media).</p>
            <p><strong>Beneficiary:</strong><br />
            UAE Nationals (18 and above)<br />
            UAE Residents (21 and above)</p>
          </div>
          <div className="service-cost">
            <div className="service-cost-label">Service Cost</div>
            <div className="service-cost-row">
              <span>1 Year</span>
              <span className="service-cost-amount">₿1000</span>
            </div>
          </div>
        </div>
      </div>

      {/* AI Info Banner */}
      <div className="ai-info-banner">
        <Sparkles size={16} style={{ flexShrink: 0, marginTop: 1 }} />
        <span>The information below has been identified and populated using AI based on your uploaded documents.</span>
      </div>

      {/* Ibdaa Details – Section 1 */}
      <div className="section-card">
        <div className="section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Ibdaa Details</span>
          {formData.tradeName && (
            <button
              type="button"
              className="btn-suggest-mini"
              onClick={handleReMatchActivity}
              disabled={matchingLoading}
              title="Re-match suitable activity for this trade name"
            >
              <RefreshCw size={12} className={matchingLoading ? 'animate-spin' : ''} />
              {matchingLoading ? 'Matching Activity...' : 'Re-match Activity'}
            </button>
          )}
        </div>
        <div style={{ marginTop: 16 }}>
          <div className="form-grid">
            <InputField
              label="Trade Name"
              value={formData.tradeName}
              onChange={(v) => updateFormData({ tradeName: v })}
              status={status('tradeName')}
              placeholder="Enter trade name"
            />
            <InputField
              label="Main Activity"
              value={formData.mainActivity}
              onChange={(v) => updateFormData({ mainActivity: v })}
              status={status('mainActivity')}
              placeholder="Enter main activity"
            />
          </div>

          {/* AI Activity Match Intelligence Banner */}
          {(formData.activityCategory || formData.activityReason || categories.length > 0) && (
            <div className="activity-intelligence-card">
              <div className="activity-badge-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>
                    DED Economic Category:
                  </span>
                  <span className="category-badge">
                    <Building2 size={13} />
                    {formData.activityCategory || 'Commercial & Trading'}
                  </span>
                </div>
                {formData.activityArabic && (
                  <span className="category-badge-ar" dir="rtl">
                    {formData.activityArabic}
                  </span>
                )}
              </div>

              {formData.activityReason && (
                <div className="activity-reason-box">
                  <Sparkles size={14} color="#2563eb" style={{ flexShrink: 0, marginTop: 2 }} />
                  <span>{formData.activityReason}</span>
                </div>
              )}

              {/* Quick Pick Representative Activities */}
              {(() => {
                const activeCat =
                  categories.find(
                    (c) =>
                      c.name_en === formData.activityCategory ||
                      c.representative_activities?.includes(formData.mainActivity)
                  ) ||
                  categories.find((c) =>
                    c.representative_activities?.some(
                      (a) =>
                        formData.mainActivity &&
                        (a.toLowerCase().includes(formData.mainActivity.toLowerCase()) ||
                          formData.mainActivity.toLowerCase().includes(a.toLowerCase()))
                    )
                  ) ||
                  categories[0]

                if (!activeCat?.representative_activities) return null

                return (
                  <div className="activity-quick-picks">
                    <div className="activity-quick-picks-label">
                      Approved Activities for {activeCat.name_en}:
                    </div>
                    <div className="quick-pick-chips">
                      {activeCat.representative_activities.map((act) => {
                        const isSelected = formData.mainActivity?.toLowerCase() === act.toLowerCase()
                        return (
                          <button
                            key={act}
                            type="button"
                            className={`quick-pick-chip ${isSelected ? 'selected' : ''}`}
                            onClick={() => {
                              updateFormData({
                                mainActivity: act,
                                activityCategory: activeCat.name_en,
                              })
                            }}
                          >
                            {isSelected && <CheckCircle2 size={12} style={{ display: 'inline', marginRight: 4 }} />}
                            {act}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )
              })()}
            </div>
          )}

          {/* Activity Sections */}
          <div className="form-group" style={{ marginTop: 16 }}>
            <label className="form-label">Activity Sections</label>
            <div className="activity-chips">
              {Array.isArray(formData.activitySections) && formData.activitySections.length > 0 ? (
                formData.activitySections.map((chip, i) => (
                  <ActivityChip
                    key={i}
                    label={chip}
                    onRemove={() => handleRemoveChip(i)}
                  />
                ))
              ) : (
                <span style={{ fontSize: 13, color: '#9ca3af' }}>No activity sections extracted</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Ibdaa Details – Section 2 */}
      <div className="section-card">
        <div className="section-title">Ibdaa Details</div>
        <div style={{ marginTop: 16 }}>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Social Media Account</label>
              <div className="input-wrapper">
                <input
                  type="text"
                  className={`input-field ${status('socialMediaAccount') === 'auto_filled' ? 'status-auto' : status('socialMediaAccount') === 'needs_review' ? 'status-review' : ''}`}
                  value={formData.socialMediaAccount}
                  onChange={(e) => updateFormData({ socialMediaAccount: e.target.value })}
                  placeholder="Social media handle"
                  style={{ paddingRight: 44 }}
                />
                <div className="input-icon">
                  <QrCode size={17} color="#9ca3af" />
                </div>
              </div>
            </div>
            <InputField
              label="License Mobile Number"
              value={formData.licenseMobileNumber}
              onChange={(v) => updateFormData({ licenseMobileNumber: v })}
              status={status('licenseMobileNumber')}
              placeholder="Enter mobile number"
            />
            <div className="form-col-full">
              <InputField
                label="License Email"
                value={formData.licenseEmail}
                onChange={(v) => updateFormData({ licenseEmail: v })}
                status={status('licenseEmail')}
                placeholder="Enter email"
                type="email"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Location Details */}
      <div className="section-card">
        <div className="section-title">Location Details</div>
        <div style={{ marginTop: 16 }}>
          <div className="location-grid">
            <div className="location-fields">
              <InputField
                label="Location"
                value={formData.location}
                onChange={(v) => updateFormData({ location: v })}
                status={status('location')}
                placeholder="Enter location"
              />
              <InputField
                label="Address"
                value={formData.address}
                onChange={(v) => updateFormData({ address: v })}
                status={status('address')}
                placeholder="Enter address"
              />
              <InputField
                label="Makani Number"
                value={formData.makaniNumber}
                onChange={(v) => updateFormData({ makaniNumber: v })}
                status={status('makaniNumber')}
                placeholder="Enter makani number"
              />
            </div>
            <Suspense fallback={<div className="map-container" style={{ background: '#f3f4f8', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: '#9ca3af' }}>Loading map...</div>}>
              <MapView
                latitude={formData.latitude}
                longitude={formData.longitude}
                onLocationResolved={handleLocationResolved}
              />
            </Suspense>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="btn-group">
        <button className="btn btn-secondary" onClick={() => navigate('/services/ibdaa-license')}>
          Back
        </button>
        <button
          className="btn btn-primary"
          onClick={() => navigate('/services/ibdaa-license/validate')}
        >
          Continue
        </button>
      </div>
    </Layout>
  )
}
