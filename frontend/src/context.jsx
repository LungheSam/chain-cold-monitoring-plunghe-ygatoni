// React context: the data source, the signed-in user and their role, and the live unit.
import { createContext, useContext, useEffect, useState } from 'react';
import { UNIT_ID } from './config.js';

const DataContext = createContext(null);

export function DataProvider({ data, children }) {
  const [user, setUser] = useState(undefined); // undefined = still checking
  const [role, setRole] = useState(null);

  useEffect(() => data.auth.onChange(async (u) => {
    if (u) {
      try {
        setRole(await data.getRole(u.uid));
      } catch {
        setRole(null);
      }
    } else {
      setRole(null);
    }
    setUser(u);
  }), [data]);

  return <DataContext.Provider value={{ data, user, role }}>{children}</DataContext.Provider>;
}

export function useData() {
  return useContext(DataContext);
}

// The live unit document (real-time listener)
export function useUnit(unitId = UNIT_ID) {
  const { data } = useData();
  const [unit, setUnit] = useState(undefined);
  useEffect(() => data.subscribeUnit(unitId, setUnit), [data, unitId]);
  return unit;
}

// Current time, refreshed every `ms` (for "last updated 12 s ago")
export function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(timer);
  }, [ms]);
  return now;
}

// Subscribe with any data.subscribeX(unitId, ..., cb) function
export function useSubscription(subscribe, deps) {
  const [value, setValue] = useState(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => subscribe(setValue), deps);
  return value;
}
