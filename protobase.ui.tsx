import { ActionInputError, defineUi, type ActionContext } from '@protobase/ui'
import type { Verification } from './functions/_shared/support-pin'

// The app's own React code, each component in a file of its own, exported by the name its layouts declare.
export { PhoneCallRoom } from './components/phone-call-room'

// The app's own handlers of the actions its views name: each calls a function of the app, which checks the caller and
// writes with rights of its own, so staff never write a call's customer or a PIN's hash themselves.

const keyOf = ({ record }: ActionContext) => Number(record?.id)

const setSupportPin = async (context: ActionContext) => {
  await context.client.invoke('set-support-pin', { body: { customer: keyOf(context), pin: context.values?.pin } })
}

const unlockSupportPin = async (context: ActionContext) => {
  await context.client.invoke('unlock-support-pin', { body: { customer: keyOf(context) } })
}

const verifyCaller = async (context: ActionContext) => {
  const body = { phone_call: keyOf(context), customer_number: context.values?.customer_number, pin: context.values?.pin }
  const answer = await context.client.invoke<Verification>('verify-caller', { body })
  if (answer.verified) return
  if (answer.triesLeft === 0) throw new ActionInputError({ pin: 'This call cannot verify the caller anymore' })
  const tries = answer.triesLeft === 1 ? '1 more try' : `${answer.triesLeft} more tries`
  throw new ActionInputError({ pin: `The customer number or PIN is wrong: ${tries} on this call` })
}

export default defineUi({ actions: { setSupportPin, unlockSupportPin, verifyCaller } })
