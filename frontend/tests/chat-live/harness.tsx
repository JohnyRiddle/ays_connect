// Isolated test entry point: real production task UI, synthetic API supplied by Playwright.
import React from 'react';
import {createRoot} from 'react-dom/client';
import {ProductionWorkRouter} from '../../src/work';
import '../../src/design-tokens.css';
import '../../src/styles.css';
import '../../src/design-system.css';
import '../../src/work.css';
import '../../src/tasks.css';
import '../../src/task-discussion.css';
createRoot(document.getElementById('root')!).render(<ProductionWorkRouter path="/tasks/task-1" navigate={()=>{}} employeeId={sessionStorage.getItem('access')||undefined}/>);
