import 'leaflet/dist/leaflet.css'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import { useEffect, useState } from 'react'

// Fix Leaflet default marker icon in Vite
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

function validCoordinate(value, min, max) {
  if (value === null || value === undefined || String(value).trim() === '') return false
  const number = Number(value)
  return Number.isFinite(number) && number >= min && number <= max
}

async function reverseGeocode(latitude, longitude, signal) {
  const query = new URLSearchParams({
    lat: String(latitude),
    lon: String(longitude),
    format: 'jsonv2',
    addressdetails: '1',
  })
  const response = await fetch(
    `https://nominatim.openstreetmap.org/reverse?${query.toString()}`,
    { signal }
  )
  if (!response.ok) throw new Error(`Coordinate lookup failed (${response.status})`)
  const data = await response.json()
  const parts = data.address || {}
  const location =
    parts.suburb ||
    parts.neighbourhood ||
    parts.village ||
    parts.town ||
    parts.city ||
    parts.county ||
    ''

  if (!data.display_name && !location) {
    throw new Error('No address was found for the site-plan coordinates')
  }
  return {
    location: location || data.display_name,
    address: data.display_name || location,
  }
}

export default function MapView({
  latitude,
  longitude,
  onLocationResolved,
}) {
  const [markerLabel, setMarkerLabel] = useState('')
  const [lookupError, setLookupError] = useState('')
  const hasCoordinates =
    validCoordinate(latitude, -90, 90) && validCoordinate(longitude, -180, 180)
  const numericLatitude = hasCoordinates ? Number(latitude) : null
  const numericLongitude = hasCoordinates ? Number(longitude) : null
  const coords =
    hasCoordinates ? [numericLatitude, numericLongitude] : null

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    async function resolveCoordinates() {
      setLookupError('')
      if (!hasCoordinates) {
        setMarkerLabel('')
        return
      }
      setMarkerLabel(`${latitude}, ${longitude}`)
      try {
        const resolved = await reverseGeocode(
          numericLatitude,
          numericLongitude,
          controller.signal
        )
        if (active) {
          setMarkerLabel(resolved.address)
          onLocationResolved?.(resolved)
        }
      } catch (error) {
        if (active && error.name !== 'AbortError') {
          setLookupError('Showing the supplied coordinates; address lookup failed.')
        }
      }
    }

    resolveCoordinates()
    return () => {
      active = false
      controller.abort()
    }
  }, [
    hasCoordinates,
    latitude,
    longitude,
    numericLatitude,
    numericLongitude,
    onLocationResolved,
  ])

  return (
    <>
      {coords ? (
        <div className="map-container">
          <MapContainer
            center={coords}
            zoom={18}
            style={{ width: '100%', height: '100%' }}
            key={coords.join(',')}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; OpenStreetMap contributors'
            />
            <Marker position={coords}>
              <Popup>{markerLabel}</Popup>
            </Marker>
          </MapContainer>
        </div>
      ) : (
        <div
          className="map-container"
          role="status"
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280' }}
        >
          Coordinates not found in the uploaded site plan.
        </div>
      )}
      {lookupError && (
        <div role="status" style={{ marginTop: 6, color: '#92400e', fontSize: 12 }}>
          {lookupError}
        </div>
      )}
    </>
  )
}
