<script setup lang="ts">
import Swal from 'sweetalert2'
import { computed, onMounted, onUnmounted, ref } from 'vue'

type Mode = 'landing' | 'license' | 'renewal' | 'bootstrap' | 'login' | 'dashboard'
const mode = ref<Mode>('landing')
const message = ref('')
const company = ref('')
const currentUser = ref('')
const dashboard = ref({ edition: '', validUntil: '', maxUsers: 0, maxBranches: 0, modules: [] as string[], userCount: 0, branchCount: 0, isAdmin: false })
const licenseStatus = ref({ status: 'no_license', days_remaining: 0, created_at: '', valid_until: '', server_date: '' })
const remainingSeconds = ref(0)
const activation = ref('')
const email = ref('admin@empresa.local')
const password = ref('')
const passwordConfirmation = ref('')
const passwordVisible = ref(false)
const passwordConfirmationVisible = ref(false)
const loginPasswordVisible = ref(false)
const licenseFile = ref<File | null>(null)
const customers = ref<Array<{ id: string; name: string; email: string | null; phone: string | null }>>([])
const customerName = ref('')
const customerEmail = ref('')
const customerPhone = ref('')
const customerMessage = ref('')
const branches = ref<Array<{ id: string; name: string; is_active: boolean }>>([])
const branchName = ref('')
const branchMessage = ref('')
const emailTouched = ref(false)
const loginEmailTouched = ref(false)

const knownTlds = new Set(['com', 'es', 'net', 'org', 'co', 'bo', 'pe', 'mx', 'ar', 'cl', 'us', 'app', 'dev', 'io', 'biz', 'info'])
const validEmail = computed(() => {
  const value = email.value.trim().toLowerCase()
  const match = value.match(/^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@([a-z0-9-]+\.)+([a-z]{2,})$/)
  return Boolean(match && knownTlds.has(match[2]))
})
const emailError = computed(() => !emailTouched.value || !email.value ? '' : validEmail.value ? '' : 'Introduce un correo con un dominio válido, por ejemplo admin@empresa.com.')
const loginEmailError = computed(() => !loginEmailTouched.value || !email.value ? '' : validEmail.value ? '' : 'Introduce un correo electrónico válido.')
const passwordRules = computed(() => ({
  length: password.value.length >= 12,
  upper: /[A-Z]/.test(password.value),
  lower: /[a-z]/.test(password.value),
  number: /\d/.test(password.value),
  symbol: /[^A-Za-z0-9]/.test(password.value),
  match: password.value.length > 0 && password.value === passwordConfirmation.value,
}))
const remainingLabel = computed(() => {
  const total = Math.max(remainingSeconds.value, 0)
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  return `${days}d ${String(hours).padStart(2, '0')}h ${String(minutes).padStart(2, '0')}m ${String(seconds).padStart(2, '0')}s`
})

function choose(event: Event) { licenseFile.value = (event.target as HTMLInputElement).files?.[0] ?? null }
function openImport() { message.value = ''; mode.value = 'license' }
function goLanding() { message.value = ''; mode.value = 'landing' }

async function requestActivation() {
  const response = await fetch('/api/license/activation-request', { method: 'POST' })
  if (!response.ok) { message.value = 'No se pudo generar la solicitud de activación.'; return }
  const data = await response.json()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'codivis-one-activation-request.json'
  link.click()
  URL.revokeObjectURL(url)
  message.value = 'Solicitud descargada. Envíala al emisor de licencias.'
}

async function refreshLicenseStatus() {
  if (mode.value !== 'dashboard') return
  const response = await fetch('/api/license/status')
  if (!response.ok) return
  const data = await response.json()
  licenseStatus.value = data
  remainingSeconds.value = data.seconds_remaining || 0
  if (data.status === 'expired' || data.status === 'invalid_license' || data.status === 'no_license') {
    message.value = data.status === 'invalid_license' ? 'La licencia no es válida. Importa una licencia firmada por Codivis.' : 'La licencia ha vencido. Importa una renovación para continuar.'
    mode.value = 'renewal'
  }
}

async function openLogin() {
  const response = await fetch('/api/license/status')
  const data = await response.json()
  licenseStatus.value = data
  if (data.status === 'expired' || data.status === 'invalid_license') { message.value = data.status === 'invalid_license' ? 'La licencia no es válida. Importa una licencia firmada por Codivis.' : 'La licencia ha vencido. Importa una renovación para continuar.'; mode.value = 'renewal' }
  else if (!data.licensed) { message.value = 'No tienes una licencia activa. Importa una licencia para continuar.'; mode.value = 'license' }
  else if (!data.admin_created) { company.value = data.company_name; message.value = 'La licencia está activa. Primero debes crear el administrador.'; mode.value = 'bootstrap' }
  else mode.value = 'login'
}

async function importLicense() {
  if (!licenseFile.value) { message.value = 'Selecciona una licencia.'; return }
  const form = new FormData(); form.append('file', licenseFile.value)
  const response = await fetch('/api/license/import', { method: 'POST', body: form })
  const data = await response.json()
  if (!response.ok) { message.value = data.detail || data.error; return }
  company.value = data.company_name
  activation.value = data.activation_token
  const statusResponse = await fetch('/api/license/status')
  const status = await statusResponse.json()
  if (status.admin_created) { message.value = 'Renovación válida. Inicia sesión para continuar.'; mode.value = 'login' }
  else { message.value = 'Licencia válida. Crea el administrador inicial.'; mode.value = 'bootstrap' }
}

async function bootstrap() {
  if (!validEmail.value) { await Swal.fire({ icon: 'warning', title: 'Correo no válido', text: 'Introduce un correo electrónico válido.' }); return }
  if (!Object.values(passwordRules.value).every(Boolean)) { await Swal.fire({ icon: 'warning', title: 'Contraseña no válida', text: 'Completa todos los requisitos indicados.' }); return }
  const response = await fetch('/api/auth/bootstrap', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ activation_token: activation.value, email: email.value, password: password.value, password_confirmation: passwordConfirmation.value }) })
  const data = await response.json()
  if (!response.ok) { await Swal.fire({ icon: 'error', title: 'No se pudo crear el administrador', text: Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail }); return }
  await Swal.fire({ icon: 'success', title: 'Administrador creado', text: 'Ya puedes iniciar sesión.' }); message.value = ''; mode.value = 'login'
}

async function login() {
  loginEmailTouched.value = true
  if (!email.value || !validEmail.value) { await Swal.fire({ icon: 'warning', title: 'Correo no válido', text: 'Introduce un correo electrónico válido.' }); return }
  if (!password.value) { await Swal.fire({ icon: 'warning', title: 'Contraseña requerida', text: 'Introduce tu contraseña.' }); return }
  const response = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: email.value, password: password.value }) })
  const data = await response.json()
  if (!response.ok) { await Swal.fire({ icon: 'error', title: 'Acceso rechazado', text: 'El usuario o la contraseña no son correctos.' }); return }
  const sessionResponse = await fetch('/api/auth/me')
  const session = await sessionResponse.json()
  if (!sessionResponse.ok) { await Swal.fire({ icon: 'error', title: 'Sesión no disponible', text: 'No se pudo cargar la sesión.' }); return }
  company.value = session.company_name
  currentUser.value = session.user_email
  dashboard.value = { edition: session.edition, validUntil: session.license_valid_until, maxUsers: session.max_users, maxBranches: session.max_branches, modules: session.modules, userCount: session.user_count, branchCount: session.branch_count, isAdmin: session.is_admin }
  await Swal.fire({ icon: 'success', title: 'Acceso correcto', text: 'Bienvenido a Codivis One.', timer: 1200, showConfirmButton: false })
  mode.value = 'dashboard'
  await loadCustomers()
  await loadBranches()
  await refreshLicenseStatus()
}

async function loadCustomers() {
  const response = await fetch('/api/customers')
  if (!response.ok) return
  customers.value = await response.json()
}

async function createCustomer() {
  customerMessage.value = ''
  if (!customerName.value.trim()) { customerMessage.value = 'El nombre del cliente es obligatorio.'; return }
  const response = await fetch('/api/customers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: customerName.value, email: customerEmail.value || null, phone: customerPhone.value || null }),
  })
  const data = await response.json()
  if (!response.ok) { customerMessage.value = data.detail?.[0]?.msg || data.detail || 'No se pudo guardar el cliente.'; return }
  customers.value.push(data)
  customers.value.sort((a, b) => a.name.localeCompare(b.name))
  customerName.value = ''
  customerEmail.value = ''
  customerPhone.value = ''
  customerMessage.value = 'Cliente guardado.'
}

async function loadBranches() {
  const response = await fetch('/api/branches')
  if (response.ok) branches.value = await response.json()
}

async function createBranch() {
  branchMessage.value = ''
  if (!branchName.value.trim()) { branchMessage.value = 'El nombre de la sucursal es obligatorio.'; return }
  const response = await fetch('/api/branches', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: branchName.value }) })
  const data = await response.json()
  if (!response.ok) { branchMessage.value = data.detail?.[0]?.msg || data.detail || 'No se pudo guardar la sucursal.'; return }
  branches.value.push(data)
  branches.value.sort((a, b) => a.name.localeCompare(b.name))
  branchName.value = ''
  branchMessage.value = 'Sucursal guardada.'
}

let licenseTimer: number | undefined
let countdownTimer: number | undefined
onMounted(() => {
  licenseTimer = window.setInterval(refreshLicenseStatus, 60000)
  countdownTimer = window.setInterval(() => {
    if (mode.value === 'dashboard' && remainingSeconds.value > 0) remainingSeconds.value -= 1
    if (mode.value === 'dashboard' && remainingSeconds.value <= 0) refreshLicenseStatus()
  }, 1000)
})
onUnmounted(() => { if (licenseTimer) window.clearInterval(licenseTimer) })
onUnmounted(() => { if (countdownTimer) window.clearInterval(countdownTimer) })
</script>

<template>
  <main>
    <section v-if="mode === 'landing'"><h1>Bienvenido a Codivis One</h1><p>El CRM local para gestionar tu empresa.</p><button @click="openLogin">Entrar al CRM</button><button class="secondary" @click="requestActivation">Solicitar activación</button><button class="secondary" @click="openImport">Importar licencia</button></section>
    <section v-else-if="mode === 'license' || mode === 'renewal'"><h1>{{ mode === 'renewal' ? 'Renovar licencia' : 'Activar Codivis One' }}</h1><p>{{ message || (mode === 'renewal' ? 'La licencia ha vencido. Importa el archivo de renovación.' : 'No tienes una licencia activa. Importa el archivo firmado por Codivis.') }}</p><input type="file" accept=".json" @change="choose"><button @click="importLicense">{{ mode === 'renewal' ? 'Importar renovación' : 'Importar licencia' }}</button><button class="secondary" @click="goLanding">Volver</button></section>
    <section v-else-if="mode === 'bootstrap'"><h1>Configurar administrador</h1><p>Empresa: {{ company }}</p><input v-model="email" type="email" placeholder="Correo electrónico" :class="{invalid: emailError}" @blur="emailTouched = true"><p v-if="emailError" class="field-error">{{ emailError }}</p><div class="password-wrap"><input v-model="password" :type="passwordVisible ? 'text' : 'password'" minlength="12" placeholder="Contraseña"><button class="password-toggle" type="button" @click="passwordVisible = !passwordVisible">{{ passwordVisible ? 'Ocultar' : 'Ver' }}</button></div><div class="requirements"><div :class="{valid: passwordRules.length}">✓ Mínimo 12 caracteres</div><div :class="{valid: passwordRules.upper}">✓ Una letra mayúscula</div><div :class="{valid: passwordRules.lower}">✓ Una letra minúscula</div><div :class="{valid: passwordRules.number}">✓ Un número</div><div :class="{valid: passwordRules.symbol}">✓ Un símbolo</div></div><div class="password-wrap"><input v-model="passwordConfirmation" :type="passwordConfirmationVisible ? 'text' : 'password'" minlength="12" placeholder="Repetir contraseña"><button class="password-toggle" type="button" @click="passwordConfirmationVisible = !passwordConfirmationVisible">{{ passwordConfirmationVisible ? 'Ocultar' : 'Ver' }}</button></div><p v-if="passwordConfirmation && !passwordRules.match" class="field-error">Las contraseñas no coinciden.</p><button @click="bootstrap">Crear administrador</button></section>
    <section v-else-if="mode === 'login'"><h1>Acceder al CRM</h1><input v-model="email" type="email" placeholder="Correo electrónico" :class="{invalid: loginEmailError}" @blur="loginEmailTouched = true"><p v-if="loginEmailError" class="field-error">{{ loginEmailError }}</p><div class="password-wrap"><input v-model="password" :type="loginPasswordVisible ? 'text' : 'password'" placeholder="Contraseña"><button class="password-toggle" type="button" @click="loginPasswordVisible = !loginPasswordVisible">{{ loginPasswordVisible ? 'Ocultar' : 'Ver' }}</button></div><button @click="login">Entrar</button><button class="secondary" @click="goLanding">Volver</button></section>
    <section v-else><h1>Bienvenido al CRM</h1><p>Empresa: {{ company }}</p><p>Usuario: {{ currentUser }}</p><p>Rol: {{ dashboard.isAdmin ? 'Administrador' : 'Usuario' }}</p><p>Edición: {{ dashboard.edition }}</p><p>Licencia creada: {{ licenseStatus.created_at }}</p><p>Licencia válida hasta: {{ dashboard.validUntil }}</p><p>Tiempo restante: {{ remainingLabel }}</p><p v-if="licenseStatus.status === 'expiring'">Aviso: la licencia vence pronto. Renueva antes de que termine.</p><p>Usuarios: {{ dashboard.userCount }} / {{ dashboard.maxUsers }}</p><p>Sucursales: {{ dashboard.branchCount }} / {{ dashboard.maxBranches }}</p><p>Módulos: {{ dashboard.modules.join(', ') || 'Ninguno' }}</p><p>La instalación está activa.</p><hr><h2>Clientes</h2><div class="customer-form"><input v-model="customerName" placeholder="Nombre del cliente"><input v-model="customerEmail" type="email" placeholder="Correo (opcional)"><input v-model="customerPhone" placeholder="Teléfono (opcional)"><button @click="createCustomer">Guardar cliente</button></div><p v-if="customerMessage" class="message">{{ customerMessage }}</p><ul><li v-for="customer in customers" :key="customer.id"><strong>{{ customer.name }}</strong><span v-if="customer.email"> · {{ customer.email }}</span><span v-if="customer.phone"> · {{ customer.phone }}</span></li></ul><p v-if="!customers.length">Todavía no hay clientes registrados.</p><hr><h2>Sucursales</h2><div class="customer-form"><input v-model="branchName" placeholder="Nombre de la sucursal"><button @click="createBranch">Guardar sucursal</button></div><p v-if="branchMessage" class="message">{{ branchMessage }}</p><ul><li v-for="branch in branches" :key="branch.id"><strong>{{ branch.name }}</strong></li></ul><p v-if="!branches.length">Todavía no hay sucursales registradas.</p></section>
    <p class="message">{{ message }}</p>
  </main>
</template>
