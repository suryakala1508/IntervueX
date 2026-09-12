import {
  Card,
  CardHeader,
  ErrorNote,
  Loading,
  PageHeader,
  Pill,
  Stat,
  formatDate,
  formatDateTime,
} from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'

function ToolLogTable({ logs }) {
  if (!logs.length) {
    return <p className="px-5 py-6 text-sm text-ink-500">No tool calls recorded yet.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[46rem] text-left text-sm">
        <thead className="border-b border-ink-100 text-xs uppercase tracking-wide text-ink-500">
          <tr>
            <th className="px-5 py-2 font-medium">When</th>
            <th className="px-5 py-2 font-medium">Tool</th>
            <th className="px-5 py-2 font-medium">Result</th>
            <th className="px-5 py-2 text-right font-medium">Took</th>
            <th className="px-5 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100">
          {logs.map((log) => (
            <tr key={log.id} className="align-top">
              <td className="whitespace-nowrap px-5 py-2 text-xs text-ink-500">
                {formatDateTime(log.created_at)}
              </td>
              <td className="px-5 py-2 font-medium text-ink-800">{log.tool_name}</td>
              <td className="max-w-md px-5 py-2 text-xs text-ink-600">
                <span className="line-clamp-2">{log.error ?? log.result_summary}</span>
              </td>
              <td className="whitespace-nowrap px-5 py-2 text-right text-xs tabular-nums text-ink-500">
                {log.duration_ms} ms
              </td>
              <td className="px-5 py-2">
                <Pill tone={log.ok ? 'good' : 'bad'}>{log.ok ? 'ok' : 'failed'}</Pill>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Admin() {
  const overview = useAsync(() => api.admin.overview(), [])
  const users = useAsync(() => api.admin.users(), [])
  const logs = useAsync(() => api.admin.toolLogs(50), [])

  if (overview.loading) return <Loading label="Loading the admin view" />
  if (overview.error) return <ErrorNote error={overview.error} onRetry={overview.reload} />

  return (
    <>
      <PageHeader
        title="Administration"
        subtitle="Platform activity and the audit trail of every AI tool call."
      />

      <section className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Users" value={overview.data.total_users} />
        <Stat label="Interviews" value={overview.data.total_interviews} />
        <Stat label="Completed" value={overview.data.completed_interviews} />
        <Stat
          label="Average score"
          value={overview.data.average_score === null ? '--' : `${overview.data.average_score}/10`}
        />
      </section>

      <div className="space-y-6">
        <Card>
          <CardHeader title="Users" subtitle="Everyone with an account" />
          {users.loading ? (
            <Loading label="Loading users" />
          ) : users.error ? (
            <div className="p-5">
              <ErrorNote error={users.error} onRetry={users.reload} />
            </div>
          ) : (
            <ul className="divide-y divide-ink-100">
              {users.data.map((user) => (
                <li
                  key={user.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-ink-900">{user.full_name}</p>
                    <p className="text-xs text-ink-500">{user.email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Pill tone={user.role === 'admin' ? 'brand' : 'neutral'}>{user.role}</Pill>
                    {!user.is_active && <Pill tone="bad">disabled</Pill>}
                    <span className="text-xs text-ink-400">
                      joined {formatDate(user.created_at)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader
            title="AI tool audit trail"
            subtitle="The workflow never touches the database directly - every read and write goes through a validated tool, and lands here."
          />
          {logs.loading ? (
            <Loading label="Loading tool logs" />
          ) : logs.error ? (
            <div className="p-5">
              <ErrorNote error={logs.error} onRetry={logs.reload} />
            </div>
          ) : (
            <ToolLogTable logs={logs.data} />
          )}
        </Card>
      </div>
    </>
  )
}
