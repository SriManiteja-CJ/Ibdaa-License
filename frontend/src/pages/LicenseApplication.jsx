import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Wand2, Info } from 'lucide-react'
import Layout from '../components/layout/Layout'
import HeroBanner from '../components/layout/HeroBanner'
import InputField from '../components/ui/InputField'
import UploadField from '../components/ui/UploadField'
import Stepper from '../components/ui/Stepper'
import { useApplication } from '../context/ApplicationContext'
import { analyzeDocuments } from '../services/api'

const STEPS = ['Upload Documents', 'Review Details', 'Validate & Submit']

export default function LicenseApplication() {
  const navigate = useNavigate()
  const { applicant, uploadedFiles, setUploadedFiles, applyExtraction } = useApplication()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleAnalyze = async () => {
    if (!uploadedFiles.screenshot && !uploadedFiles.sitePlan) {
      setError('Please upload at least one document before analyzing.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const result = await analyzeDocuments(
        uploadedFiles.screenshot,
        uploadedFiles.sitePlan,
        uploadedFiles.socialMediaUrl
      )
      if (!result.document_validation?.is_valid) {
        const issues = result.document_validation?.issues || []
        setError(
          issues.length
            ? `Please check your uploaded documents:\n${issues.join('\n')}`
            : 'The uploaded documents could not be confirmed as the expected types. Please check them and try again.'
        )
        return
      }
      applyExtraction(result.extraction)
      navigate('/services/ibdaa-license/review')
    } catch (err) {
      setError(err?.response?.data?.detail || 'Analysis failed. Please check your backend connection.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      {loading && (
        <div className="loading-overlay">
          <div className="spinner" />
          <div className="loading-text">Analyzing Documents with AI...</div>
          <div className="loading-sub">This may take up to 30 seconds</div>
        </div>
      )}

      <HeroBanner
        eyebrow="DED Smart Services - Service Catalogue"
        title="Ibdaa License"
      />

      <Stepper steps={STEPS} current={0} />

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

      {/* Applicant Details */}
      <div className="section-card">
        <div className="section-title">Applicant Details</div>
        <div style={{ marginTop: 16 }}>
          <div className="form-grid cols-3">
            <InputField
              label="Active Email ID"
              value={applicant.email}
              status="verified"
              readOnly
            />
            <InputField
              label="Active Mobile No."
              value={applicant.mobile}
              status="verified"
              readOnly
            />
            <InputField
              label="Emirates ID No."
              value={applicant.emiratesId}
              status="verified"
              readOnly
            />
          </div>
        </div>
      </div>

      {/* Upload Documents */}
      <div className="section-card">
        <div className="section-title">Upload Mandatory Document</div>
        <div style={{ marginTop: 16 }}>
          <div className="form-grid">
            <UploadField
              label="Social Media Page Screenshot"
              file={uploadedFiles.screenshot}
              onFileChange={(f) => setUploadedFiles((p) => ({ ...p, screenshot: f }))}
              accept="image/*,application/pdf"
            />
            <UploadField
              label="Upload Valid Site Plan"
              file={uploadedFiles.sitePlan}
              onFileChange={(f) => setUploadedFiles((p) => ({ ...p, sitePlan: f }))}
              accept="image/*,application/pdf"
            />
            <div className="form-col-full">
              <InputField
                label="Social Media Page URL"
                value={uploadedFiles.socialMediaUrl}
                onChange={(v) => setUploadedFiles((p) => ({ ...p, socialMediaUrl: v }))}
                placeholder="Enter the URL"
              />
            </div>
          </div>

          {error && (
            <div style={{ marginTop: 12, display: 'flex', alignItems: 'flex-start', gap: 8, color: '#dc2626', fontSize: 13, whiteSpace: 'pre-line' }}>
              <Info size={15} /> {error}
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="btn-group">
        <button className="btn btn-secondary" onClick={() => navigate('/services')}>
          Cancel
        </button>
        <button className="btn btn-primary" onClick={handleAnalyze} disabled={loading}>
          <Wand2 size={16} />
          Analyze with AI
        </button>
      </div>
    </Layout>
  )
}
