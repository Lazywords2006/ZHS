import * as mockApi from './mock'
import * as realApi from './real'

const useMock = import.meta.env.VITE_USE_MOCK !== 'false'

export const fetchAccounts = useMock ? mockApi.fetchAccounts : realApi.fetchAccounts
export const fetchCourses = useMock ? mockApi.fetchCourses : realApi.fetchCourses
export const createAccount = useMock ? mockApi.createAccount : realApi.createAccount
export const deleteAccount = useMock ? mockApi.deleteAccount : realApi.deleteAccount
export const saveAccountConfig = useMock ? mockApi.saveAccountConfig : realApi.saveAccountConfig
export const fetchQrCode = useMock ? mockApi.fetchQrCode : realApi.fetchQrCode
export const refreshQrCode = useMock ? mockApi.refreshQrCode : realApi.refreshQrCode
export const fetchQrStatus = useMock ? mockApi.fetchQrStatus : realApi.fetchQrStatus
export const startRun = useMock ? mockApi.startRun : realApi.startRun
export const stopRun = useMock ? mockApi.stopRun : realApi.stopRun
