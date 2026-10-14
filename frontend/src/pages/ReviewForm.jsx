import { useCallback, useEffect, lazy, Suspense } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, QrCode } from 'lucide-react'
import Layout from '../components/layout/Layout'
import HeroBanner from '../components/layout/HeroBanner'
import InputField from '../components/ui/InputField'
import ActivityChip from '../components/ui/ActivityChip'
import Stepper from '../components/ui/Stepper'
import { useApplication } from '../context/ApplicationContext'

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

  useEffect(() => {
    // If no extraction, go back to upload
    if (!extraction) navigate('/services/ibdaa-license')
  }, [extraction, navigate])

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
        <div className="section-title">Ibdaa Details</div>
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
