export default function Header() {
  return (
    <header className="header">
      <div className="header-logo">
        <img
          src="/assets/ded-logo.png"
          alt="Government of Umm Al Quwain - Department of Economic Development"
          className="header-brand-logo"
        />
      </div>

      <div className="header-right">
        <div className="header-lang-badge">ع</div>
        <div className="header-user">
          <div className="header-user-name">Abdullah<br />Mohammed</div>
          <div className="header-avatar">AM</div>
        </div>
      </div>
    </header>
  )
}
