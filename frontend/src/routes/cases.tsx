import { createFileRoute } from '@tanstack/react-router'
import CasesPage from '@/pages/CasesPage'

export const Route = createFileRoute('/cases')({
  component: CasesPage,
})
