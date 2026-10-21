import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import HeroBanner from '../components/layout/HeroBanner'
import Stepper from '../components/ui/Stepper'
import { useApplication } from '../context/ApplicationContext'
import { submitApplication } from '../services/api'

const STEPS = ['Upload Documents', 'Review Details', 'Validate & Submit']

export default function ValidateSubmit() {
  const navigate = useNavigate()
  const { formData, updateFormData, applicant, setSubmissionResult } = useApplication()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fees = {
    license: 1000,
    electronicService: 0,
    electronicPayment: 0.55,
    other: 40.65,
  }
  const total = Object.values(fees).reduce((a, b) => a + b, 0)

  const handleSubmit = async () => {
    if (!formData.termsAccepted) {
      setError('Please accept the Terms and Conditions.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const result = await submitApplication({
        email: applicant.email,
        mobile: applicant.mobile,
        emirates_id: applicant.emiratesId,
        trade_name: formData.tradeName,
        main_activity: formData.mainActivity,
        activity_sections: Array.isArray(formData.activitySections) ? formData.activitySections : [],
        social_media_account: formData.socialMediaAccount,
        license_mobile_number: formData.licenseMobileNumber,
        license_email: formData.licenseEmail,
        social_media_url: formData.socialMediaUrl || '',
        location: formData.location,
        address: formData.address,
        makani_number: formData.makaniNumber,
        terms_accepted: formData.termsAccepted,
      })
      setSubmissionResult(result)
      navigate('/services/ibdaa-license/success')
    } catch (err) {
      setError(err?.response?.data?.detail || 'Submission failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      {loading && (
        <div className="loading-overlay">
          <div className="spinner" />
          <div className="loading-text">Submitting Application...</div>
        </div>
      )}

      <HeroBanner
        eyebrow="DED Smart Services - Service Catalogue"
        title="Ibdaa License"
      />

      <Stepper steps={STEPS} current={2} />

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

      {/* Trade Name Validation */}
      <div className="section-card">
        <div className="section-title">Validate your Trade Name</div>
        <div style={{ marginTop: 16 }}>
          <div className="validate-row">
            <div className="validate-label">Trade Name</div>
            <div>
              <div className="validate-value">{formData.tradeName || '—'}</div>
              {formData.tradeNameArabic && (
                <div className="validate-value-sub">{formData.tradeNameArabic}</div>
              )}
            </div>
          </div>
          <div className="validate-row">
            <div className="validate-label">Activity</div>
            <div>
              <div className="validate-value">{formData.mainActivity || '—'}</div>
              {formData.activityCategory && (
                <div style={{ fontSize: 12, color: '#4f46e5', fontWeight: 500, marginTop: 2 }}>
                  Category: {formData.activityCategory}
                </div>
              )}
              {formData.activityArabic && (
                <div className="validate-value-sub">{formData.activityArabic}</div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Fees */}
      <div className="section-card">
        <div className="section-title" style={{ marginBottom: 12 }}>Fees</div>
        <div className="fees-table">
          <div className="fees-row">
            <span>Ibdaa License (1 Year)</span>
            <span className="fees-amount">₿ {fees.license.toFixed(2)}</span>
          </div>
          <div className="fees-row">
            <span>Electronic service fee</span>
            <span className="fees-amount">₿ {fees.electronicService.toFixed(2)}</span>
          </div>
          <div className="fees-row">
            <span>Electronic Payment Fees</span>
            <span className="fees-amount">₿ {fees.electronicPayment.toFixed(2)}</span>
          </div>
          <div className="fees-row">
            <span>Other Fees</span>
            <span className="fees-amount">₿ {fees.other.toFixed(2)}</span>
          </div>
          <div className="fees-row total">
            <span>Total Cost</span>
            <span className="fees-amount">₿ {total.toFixed(2)}</span>
          </div>
        </div>

        {/* T&C */}
        <div className="checkbox-row">
          <input
            id="terms"
            type="checkbox"
            checked={formData.termsAccepted}
            onChange={(e) => updateFormData({ termsAccepted: e.target.checked })}
          />
          <label htmlFor="terms" className="checkbox-label">
            I've read and accept the Terms and Conditions
          </label>
        </div>

        {error && (
          <div style={{ marginTop: 10, color: '#dc2626', fontSize: 13 }}>{error}</div>
        )}
      </div>

      {/* Actions */}
      <div className="btn-group">
        <button className="btn btn-secondary" onClick={() => navigate('/services/ibdaa-license/review')}>
          Cancel
        </button>
        <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
          Submit
        </button>
      </div>
    </Layout>
  )
}
