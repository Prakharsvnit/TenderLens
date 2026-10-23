import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserPool,
  CognitoUserSession,
} from 'amazon-cognito-identity-js'
import { config } from './config'

const LOCAL_USER = 'demo@tenderlens.local'

function pool(): CognitoUserPool {
  const c = config()
  return new CognitoUserPool({ UserPoolId: c.userPoolId!, ClientId: c.userPoolClientId! })
}

export type SignInResult = { ok: true } | { newPasswordRequired: true; user: CognitoUser }

export function signIn(email: string, password: string): Promise<SignInResult> {
  const user = new CognitoUser({ Username: email, Pool: pool() })
  return new Promise((resolve, reject) => {
    user.authenticateUser(new AuthenticationDetails({ Username: email, Password: password }), {
      onSuccess: () => resolve({ ok: true }),
      onFailure: (err) => reject(err),
      newPasswordRequired: () => resolve({ newPasswordRequired: true, user }),
    })
  })
}

export function completeNewPassword(user: CognitoUser, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    user.completeNewPasswordChallenge(password, {}, { onSuccess: () => resolve(), onFailure: reject })
  })
}

function currentSession(): Promise<CognitoUserSession | null> {
  const user = pool().getCurrentUser()
  if (!user) return Promise.resolve(null)
  return new Promise((resolve) => {
    user.getSession((err: Error | null, session: CognitoUserSession | null) =>
      resolve(err || !session?.isValid() ? null : session),
    )
  })
}

/** The Cognito ID token for the API's JWT authorizer, or null when signed out. Local dev needs none. */
export async function idToken(): Promise<string | null> {
  if (config().local) return 'local'
  const session = await currentSession()
  return session ? session.getIdToken().getJwtToken() : null
}

export async function currentEmail(): Promise<string | null> {
  if (config().local) return LOCAL_USER
  const session = await currentSession()
  return session ? (session.getIdToken().payload.email as string) : null
}

export function signOut(): void {
  if (!config().local) pool().getCurrentUser()?.signOut()
}
