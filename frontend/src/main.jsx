import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import '@fontsource/montserrat/400.css';
import '@fontsource/montserrat/500.css';
import '@fontsource/montserrat/600.css';
import '@fontsource/montserrat/700.css';
import '@fontsource/montserrat/800.css';
import { loadData } from './data/index.js';
import { DataProvider } from './context.jsx';
import { applyTheme, ThemeProvider } from './theme.jsx';
import App from './App.jsx';
import './styles.css';

applyTheme();   // before the first paint, so there is no flash of the wrong theme

const root = createRoot(document.getElementById('root'));

loadData()
  .then((data) => {
    root.render(
      <StrictMode>
        <ThemeProvider>
          <DataProvider data={data}>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </DataProvider>
        </ThemeProvider>
      </StrictMode>,
    );
  })
  .catch((err) => {
    root.render(<p className="page error">Could not start: {String(err.message || err)}. Check frontend/.env.local.</p>);
  });
