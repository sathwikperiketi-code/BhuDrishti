/** Display-only label for the separately launched local QA database/frontend. */
export const isQaWorkspace = import.meta.env.DEV && import.meta.env.VITE_QA_WORKSPACE === 'true'
