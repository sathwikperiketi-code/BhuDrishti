import { ArrowLeft, ArrowRight, BadgeCheck, CheckCircle2, CircleAlert, ClipboardCheck, Eye, KeyRound, Landmark, Mail, ShieldCheck } from 'lucide-react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Brand } from '../../components/Brand'
import { forgotPassword, resendVerification, resetPassword, signup, verifyEmail, type SignupValues } from './accountApi'
import { passwordHint, validEmail, validateReset, validateSignup, usernameHint, type SignupErrors } from './accountValidation'
import { registrationRoleLabel, registrationRoles, type RequestedRole } from './registrationRoles'
import { accountLinkParameter, createEmailVerificationRequest } from './emailVerification'
import { publicAuthRoute, type PublicAuthRoute } from './publicRoutes'
import './account-pages.css'

function tokenFromHash(hash: string): string {
  return accountLinkParameter(hash, 'token')
}

function emailFromHash(hash: string): string {
  return accountLinkParameter(hash, 'email')
}

function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

function Status({ tone, children }: { tone: 'success' | 'error' | 'info'; children: ReactNode }) {
  return <div className={`bd-account-status bd-account-status--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
    {tone === 'error' ? <CircleAlert size={17} aria-hidden="true" /> : <CheckCircle2 size={17} aria-hidden="true" />}
    <span>{children}</span>
  </div>
}

function AuthLayout({ children, detail, wide = false }: { children: ReactNode; detail: string; wide?: boolean }) {
  return <main className="bd-account-shell">
    <section className="bd-account-story" aria-label="About BhuDrishti AI">
      <div className="bd-account-story__brand"><Brand /></div>
      <div className="bd-account-story__content">
        <div className="bd-account-story__mark" aria-hidden="true"><ShieldCheck size={30} strokeWidth={1.5} /></div>
        <span className="bd-account-story__eyebrow">Secure record intelligence</span>
        <h1>A clearer view of every land record.</h1>
        <p>Bring document review, human verification, and a complete audit trail into one protected workspace.</p>
        <div className="bd-account-story__steps" aria-hidden="true"><span>01 &nbsp; Ingest</span><span>02 &nbsp; Examine</span><span>03 &nbsp; Verify</span></div>
      </div>
      <p className="bd-account-story__footer">AI assists. Human officers verify. This product does not determine legal ownership.</p>
    </section>
    <section className="bd-account-panel" aria-label={detail}>
      <div className={`bd-account-panel__inner ${wide ? 'bd-account-panel__inner--wide' : ''}`}>{children}</div>
      <div className="bd-account-panel__footer">BhuDrishti AI · Secure account access</div>
    </section>
  </main>
}

function AccountHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <header className="bd-account-header">
    <span className="bd-account-eyebrow">{eyebrow}</span>
    <h2>{title}</h2>
    <p>{description}</p>
  </header>
}

function FormField({ id, label, type = 'text', value, onChange, autocomplete, placeholder, disabled, error, hint, minLength, maxLength }: {
  id: string; label: string; type?: string; value: string; onChange: (value: string) => void
  autocomplete?: string; placeholder?: string; disabled?: boolean; error?: string; hint?: string
  minLength?: number; maxLength?: number
}) {
  return <div className="bd-account-field">
    <label htmlFor={id}>{label}</label>
    <input id={id} name={id} type={type} autoComplete={autocomplete} placeholder={placeholder} value={value}
      onChange={(event) => onChange(event.target.value)} disabled={disabled} required minLength={minLength} maxLength={maxLength}
      aria-invalid={Boolean(error)} aria-describedby={error || hint ? `${id}-help` : undefined} />
    {error ? <small id={`${id}-help`} className="bd-account-field__error">{error}</small> : hint ? <small id={`${id}-help`} className="bd-account-field__hint">{hint}</small> : null}
  </div>
}

function LoginPage({ loading, message, onSignIn, onClearError }: { loading: boolean; message?: string; onSignIn: (email: string, password: string) => void; onClearError: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [localError, setLocalError] = useState('')
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!validEmail(email)) { setLocalError('Enter a valid email address.'); return }
    setLocalError('')
    onSignIn(email, password)
  }
  return <AuthLayout detail="Sign in">
    <AccountHeader eyebrow="Welcome back" title="Sign in to your workspace" description="Use the email and password for your verified BhuDrishti account." />
    <form className="bd-account-form" onSubmit={submit} noValidate>
      <FormField id="login-email" label="Email address" type="email" value={email} onChange={(value) => { setEmail(value); setLocalError(''); onClearError() }} autocomplete="username" placeholder="you@example.com" disabled={loading} />
      <FormField id="login-password" label="Password" type="password" value={password} onChange={(value) => { setPassword(value); setLocalError(''); onClearError() }} autocomplete="current-password" placeholder="Enter your password" disabled={loading} />
      <div className="bd-account-form__aside"><a href="#/forgot-password">Forgot password?</a></div>
      {localError || message ? <Status tone="error">{localError || message}</Status> : null}
      <button className="bd-account-submit" type="submit" disabled={loading || !email || !password}>{loading ? 'Signing in…' : 'Sign in'}<ArrowRight size={17} aria-hidden="true" /></button>
    </form>
    <p className="bd-account-switch">New to BhuDrishti? <a href="#/signup">Create an account</a></p>
    <p className="bd-account-switch bd-account-switch--secondary">Need a new verification link? <a href="#/verify-email">Resend email</a></p>
  </AuthLayout>
}

const emptySignup: SignupValues = { fullName: '', username: '', email: '', password: '', confirmPassword: '', requestedRole: '' }

const roleIcons = {
  REVENUE_OFFICER: Landmark,
  VERIFIER: BadgeCheck,
  AUDITOR: Eye,
  ADMIN: ClipboardCheck,
}

function SignupPage() {
  const [values, setValues] = useState<SignupValues>(emptySignup)
  const [errors, setErrors] = useState<SignupErrors>({})
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [complete, setComplete] = useState(false)
  function update(field: Exclude<keyof SignupValues, 'requestedRole'>, value: string) {
    setValues((previous) => ({ ...previous, [field]: value }))
    setErrors((previous) => ({ ...previous, [field]: undefined }))
    setMessage('')
  }
  function selectRole(role: RequestedRole) {
    setValues((previous) => ({ ...previous, requestedRole: role }))
    setErrors((previous) => ({ ...previous, requestedRole: undefined }))
    setMessage('')
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validateSignup(values)
    setErrors(nextErrors)
    if (Object.values(nextErrors).some(Boolean)) return
    setBusy(true)
    setMessage('')
    try {
      await signup(values)
      setComplete(true)
      setValues((previous) => ({ ...previous, password: '', confirmPassword: '' }))
    } catch (error) { setMessage(messageOf(error, 'The account could not be created.')) }
    finally { setBusy(false) }
  }
  return <AuthLayout detail="Create an account" wide>
    {complete ? <>
      <div className="bd-account-result-icon"><Mail size={28} aria-hidden="true" /></div>
      <AccountHeader eyebrow="One more step" title="Account created." description="Check your email to verify your BhuDrishti account. Open the link we sent before signing in." />
      <Status tone="info">{values.requestedRole === 'ADMIN' ? 'Your account has been created, but administrator access is pending approval. Your email must also be verified before you can sign in.' : 'Your account will stay unverified until you follow the email link.'}</Status>
      <div className="bd-account-actions"><a className="bd-account-link-button" href={`#/verify-email?email=${encodeURIComponent(values.email.trim())}`}>Verification help <ArrowRight size={16} aria-hidden="true" /></a><a href="#/login">Back to sign in</a></div>
    </> : <>
      <AccountHeader eyebrow="Get started" title="Create your account" description="Set up your identity, then confirm your email before accessing the workspace." />
      <form className="bd-account-form" onSubmit={(event) => void submit(event)} noValidate>
        <div className="bd-account-form__row">
          <FormField id="signup-full-name" label="Full name" value={values.fullName} onChange={(value) => update('fullName', value)} autocomplete="name" placeholder="Your full name" disabled={busy} error={errors.fullName} maxLength={160} />
          <FormField id="signup-username" label="Username" value={values.username} onChange={(value) => update('username', value)} autocomplete="username" placeholder="your.name" disabled={busy} error={errors.username} hint={usernameHint} maxLength={32} />
        </div>
        <FormField id="signup-email" label="Email address" type="email" value={values.email} onChange={(value) => update('email', value)} autocomplete="email" placeholder="you@example.com" disabled={busy} error={errors.email} maxLength={254} />
        <div className="bd-account-form__row">
          <FormField id="signup-password" label="Password" type="password" value={values.password} onChange={(value) => update('password', value)} autocomplete="new-password" placeholder="Create a password" disabled={busy} error={errors.password} hint={passwordHint} minLength={12} maxLength={256} />
          <FormField id="signup-confirm-password" label="Confirm password" type="password" value={values.confirmPassword} onChange={(value) => update('confirmPassword', value)} autocomplete="new-password" placeholder="Repeat your password" disabled={busy} error={errors.confirmPassword} maxLength={256} />
        </div>
        <fieldset className="bd-role-picker" aria-describedby={errors.requestedRole ? 'bd-role-picker-error' : undefined}>
          <legend>What will you use BhuDrishti for?</legend>
          <p className="bd-role-picker__intro">Choose the role you are requesting. The service verifies and assigns your actual permissions.</p>
          <div className="bd-role-picker__grid">
            {registrationRoles.map((role) => {
              const Icon = roleIcons[role.value]
              const selected = values.requestedRole === role.value
              return <label key={role.value} className={`bd-role-card ${selected ? 'bd-role-card--selected' : ''} ${role.value === 'ADMIN' ? 'bd-role-card--restricted' : ''}`}>
                <input type="radio" name="requestedRole" value={role.value} checked={selected} onChange={() => selectRole(role.value)} disabled={busy} required />
                <span className="bd-role-card__top"><span className="bd-role-card__icon"><Icon size={20} strokeWidth={1.8} aria-hidden="true" /></span><span className="bd-role-card__radio" aria-hidden="true" /></span>
                <strong>{role.title}</strong>
                <span className="bd-role-card__description">{role.description}</span>
                <span className="bd-role-card__permissions">{role.permissions.map((permission) => <span key={permission}>{permission}</span>)}</span>
                <span className="bd-role-card__action">{selected ? 'Selected' : role.action}<ArrowRight size={14} aria-hidden="true" /></span>
              </label>
            })}
          </div>
          {errors.requestedRole ? <small id="bd-role-picker-error" className="bd-account-field__error" role="alert">{errors.requestedRole}</small> : null}
        </fieldset>
        {values.requestedRole === 'ADMIN' ? <div className="bd-role-admin-note" role="note"><ShieldCheck size={18} aria-hidden="true" /><span><strong>Administrator access requires authorization.</strong> You can verify your email and sign in with restricted access while an existing administrator reviews your request.</span></div> : null}
        <p className="bd-role-confirmation">Selected role: <strong>{registrationRoleLabel(values.requestedRole) || 'None selected'}</strong></p>
        {message ? <Status tone="error">{message}</Status> : null}
        <button className="bd-account-submit" type="submit" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}<ArrowRight size={17} aria-hidden="true" /></button>
      </form>
      <p className="bd-account-switch">Already have an account? <a href="#/login">Sign in</a></p>
      {message ? <p className="bd-account-switch bd-account-switch--secondary">Account already created? <a href={`#/verify-email?email=${encodeURIComponent(values.email.trim())}`}>Request a new verification link</a></p> : null}
    </>}
  </AuthLayout>
}

function VerifyEmailPage({ hash }: { hash: string }) {
  const token = tokenFromHash(hash)
  const [email, setEmail] = useState(() => emailFromHash(hash))
  const [outcome, setOutcome] = useState<{ phase: 'verified' | 'failed' | 'missing'; message: string }>({ phase: 'missing', message: '' })
  const phase = token ? 'checking' : outcome.phase
  const [resendStatus, setResendStatus] = useState<{ tone: 'info' | 'error'; message: string } | null>(null)
  const [resendBusy, setResendBusy] = useState(false)
  const [requestVerification] = useState(() => createEmailVerificationRequest(verifyEmail))

  useEffect(() => {
    if (!token) return
    return requestVerification(token, (result) => {
      // The browser hash can change before React runs the effect's cleanup.
      const currentHash = window.location.hash
      if (publicAuthRoute(currentHash) !== 'verify-email' || tokenFromHash(currentHash) !== token) return
      if (result.verified === true) {
        setOutcome({ phase: 'verified', message: '' })
      } else {
        setOutcome({ phase: 'failed', message: messageOf(result.error, 'This verification link could not be used.') })
      }
      setResendStatus(null)
      window.history.replaceState(null, '', '#/verify-email')
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
  }, [token, requestVerification])

  async function resend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!validEmail(email)) { setResendStatus({ tone: 'error', message: 'Enter a valid email address.' }); return }
    setResendBusy(true)
    setResendStatus(null)
    try {
      await resendVerification(email)
      setResendStatus({ tone: 'info', message: 'If this account needs verification, check your email for a new link. Allow a minute between requests.' })
    } catch (error) { setResendStatus({ tone: 'error', message: messageOf(error, 'A verification email could not be requested.') }) }
    finally { setResendBusy(false) }
  }

  return <AuthLayout detail="Email verification">
    <div className={`bd-account-result-icon bd-verification-icon bd-verification-icon--${phase}`} aria-hidden="true">
      {phase === 'checking' ? <span className="bd-verification-spinner" /> : phase === 'verified' ? <CheckCircle2 size={30} /> : phase === 'failed' ? <CircleAlert size={28} /> : <Mail size={28} />}
    </div>
    <AccountHeader eyebrow="Account verification" title={phase === 'verified' ? 'Email verified' : phase === 'checking' ? 'Verifying your email…' : phase === 'failed' ? 'Unable to verify this link' : 'Verify your email'}
      description={phase === 'verified' ? 'Your email has been confirmed. You can now sign in to your BhuDrishti workspace.' : phase === 'checking' ? 'We are checking your verification link with the account service.' : 'Use the verification link in your email to activate your account.'} />
    <div className="bd-verification-feedback">
      {phase === 'checking' ? <div className="bd-account-progress" role="status">Securely confirming your account. This may take a few seconds.</div> : null}
      {phase === 'verified' ? <Status tone="success">Your email verification is complete. Your workspace access follows your assigned role; administrator requests still require approval.</Status> : null}
      {phase === 'failed' ? <><Status tone="error">{outcome.message}</Status><p className="bd-verification-help">Verification links expire and can only be used once. If you already verified your email, sign in. Otherwise, request a new link below.</p></> : null}
      {phase === 'missing' ? <Status tone="info">Open the complete link from your verification email, or request a new link below.</Status> : null}
    </div>
    {phase === 'failed' || phase === 'missing' ? <form className="bd-account-form bd-account-resend" onSubmit={(event) => void resend(event)} noValidate>
      <FormField id="resend-email" label="Email address" type="email" value={email} onChange={setEmail} autocomplete="email" placeholder="you@example.com" disabled={resendBusy} />
      {resendStatus ? <Status tone={resendStatus.tone}>{resendStatus.message}</Status> : null}
      <button className="bd-account-submit" type="submit" disabled={resendBusy || !email}>{resendBusy ? 'Requesting…' : 'Resend verification email'}<ArrowRight size={17} aria-hidden="true" /></button>
    </form> : null}
    <div className="bd-account-actions">{phase === 'verified'
      ? <a className="bd-account-link-button" href="#/login">Go to Sign In <ArrowRight size={16} aria-hidden="true" /></a>
      : <a href="#/login"><ArrowLeft size={16} aria-hidden="true" /> Back to sign in</a>}</div>
  </AuthLayout>
}

function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [message, setMessage] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!validEmail(email)) { setMessage('Enter a valid email address.'); return }
    setBusy(true)
    setMessage('')
    try { await forgotPassword(email); setSent(true) }
    catch (error) { setMessage(messageOf(error, 'The reset email could not be requested.')) }
    finally { setBusy(false) }
  }
  return <AuthLayout detail="Forgot password">
    <div className="bd-account-result-icon"><KeyRound size={28} aria-hidden="true" /></div>
    <AccountHeader eyebrow="Account recovery" title={sent ? 'Check your inbox' : 'Reset your password'} description={sent
      ? 'If a verified, active account exists for this address, check your email for a reset link. Allow a minute between requests.'
      : 'Enter your account email to request a time limited reset link.'} />
    {sent ? <Status tone="info">For privacy, we do not confirm whether an account exists for this address.</Status> : <form className="bd-account-form" onSubmit={(event) => void submit(event)} noValidate>
      <FormField id="forgot-email" label="Email address" type="email" value={email} onChange={setEmail} autocomplete="email" placeholder="you@example.com" disabled={busy} />
      {message ? <Status tone="error">{message}</Status> : null}
      <button className="bd-account-submit" type="submit" disabled={busy || !email}>{busy ? 'Sending request…' : 'Send reset link'}<ArrowRight size={17} aria-hidden="true" /></button>
    </form>}
    <p className="bd-account-switch bd-account-switch--secondary">Reset links require a verified email. <a href={`#/verify-email?email=${encodeURIComponent(email.trim())}`}>Request a verification link</a></p>
    <div className="bd-account-actions"><a href="#/login"><ArrowLeft size={16} aria-hidden="true" /> Back to sign in</a></div>
  </AuthLayout>
}

function ResetPasswordPage({ hash }: { hash: string }) {
  const token = tokenFromHash(hash)
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errors, setErrors] = useState<{ password?: string; confirmPassword?: string }>({})
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [complete, setComplete] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validateReset(password, confirmPassword)
    setErrors(nextErrors)
    if (nextErrors.password || nextErrors.confirmPassword) return
    if (!token) { setMessage('This reset link is missing its token. Request a new link.'); return }
    setBusy(true)
    setMessage('')
    try {
      await resetPassword(token, password, confirmPassword)
      setPassword('')
      setConfirmPassword('')
      setComplete(true)
      window.history.replaceState(null, '', '#/reset-password')
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    } catch (error) { setMessage(messageOf(error, 'The password could not be reset.')) }
    finally { setBusy(false) }
  }
  return <AuthLayout detail="Reset password">
    <div className="bd-account-result-icon"><KeyRound size={28} aria-hidden="true" /></div>
    <AccountHeader eyebrow="Account recovery" title={complete ? 'Password updated' : 'Create a new password'}
      description={complete ? 'Your password has been changed. Sign in with the new password to open your workspace.' : 'Choose a strong password for your BhuDrishti account.'} />
    {complete ? <Status tone="success">Your reset was confirmed by the account service. Existing sessions may need to sign in again.</Status> : !token ? <>
      <Status tone="error">This reset link is missing its token. Request a new link.</Status>
      <div className="bd-account-actions"><a className="bd-account-link-button" href="#/forgot-password">Request a reset link <ArrowRight size={16} aria-hidden="true" /></a></div>
    </> : <form className="bd-account-form" onSubmit={(event) => void submit(event)} noValidate>
      <FormField id="reset-password" label="New password" type="password" value={password} onChange={(value) => { setPassword(value); setErrors((previous) => ({ ...previous, password: undefined })) }} autocomplete="new-password" placeholder="Create a new password" disabled={busy} error={errors.password} hint={passwordHint} minLength={12} maxLength={256} />
      <FormField id="reset-confirm-password" label="Confirm new password" type="password" value={confirmPassword} onChange={(value) => { setConfirmPassword(value); setErrors((previous) => ({ ...previous, confirmPassword: undefined })) }} autocomplete="new-password" placeholder="Repeat your new password" disabled={busy} error={errors.confirmPassword} maxLength={256} />
      {message ? <Status tone="error">{message}</Status> : null}
      <p className="bd-verification-help">Reset links expire after 30 minutes and can only be used once. <a href="#/forgot-password">Request a new reset link</a>.</p>
      <button className="bd-account-submit" type="submit" disabled={busy}>{busy ? 'Updating password…' : 'Reset password'}<ArrowRight size={17} aria-hidden="true" /></button>
    </form>}
    <div className="bd-account-actions"><a href="#/login"><ArrowLeft size={16} aria-hidden="true" /> Back to sign in</a></div>
  </AuthLayout>
}

export function AccountPage({ route, hash, loginLoading, loginMessage, onSignIn, onClearError }: {
  route: PublicAuthRoute; hash: string; loginLoading: boolean; loginMessage?: string
  onSignIn: (email: string, password: string) => void; onClearError: () => void
}) {
  switch (route) {
    case 'login': return <LoginPage loading={loginLoading} message={loginMessage} onSignIn={onSignIn} onClearError={onClearError} />
    case 'signup': return <SignupPage />
    case 'verify-email': return <VerifyEmailPage hash={hash} />
    case 'forgot-password': return <ForgotPasswordPage />
    case 'reset-password': return <ResetPasswordPage hash={hash} />
  }
}
