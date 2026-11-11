import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { loadData } from './data/index.js';
import { DataProvider } from './context.jsx';
import App from './App.jsx';
import './styles.css';

const root = createRoot(document.getElementById('root'));

loadData()
  .then((data) => {
    root.render(
      <StrictMode>
        <DataProvider data={data}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </DataProvider>
      </StrictMode>,
    );
  })
  .catch((err) => {
    root.render(<p className="page error">Could not start: {String(err.message || err)}. Check frontend/.env.local.</p>);
  });
