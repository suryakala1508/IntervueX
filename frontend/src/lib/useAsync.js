import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Run an async loader and track its loading/error/data state.
 *
 * Results from a superseded call are discarded, so a fast second load cannot be
 * overwritten by a slow first one.
 */
export function useAsync(loader, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const callId = useRef(0)

  const run = useCallback(async () => {
    const id = ++callId.current
    setState((previous) => ({ ...previous, loading: true, error: null }))
    try {
      const data = await loader()
      if (id === callId.current) setState({ data, error: null, loading: false })
      return data
    } catch (error) {
      if (id === callId.current) setState({ data: null, error, loading: false })
      return undefined
    }
    // loader is intentionally not a dependency: callers pass an inline arrow
    // function, and depending on it would re-run on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    run()
    return () => {
      // Invalidate any in-flight call so an unmounted page never sets state.
      callId.current += 1
    }
  }, [run])

  const setData = useCallback((updater) => {
    setState((previous) => ({
      ...previous,
      data: typeof updater === 'function' ? updater(previous.data) : updater,
    }))
  }, [])

  return { ...state, reload: run, setData }
}
