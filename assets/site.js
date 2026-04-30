function renderChart(containerId, chartConfig) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }

  const isTimeBased = Array.isArray(chartConfig.categories) && chartConfig.categories.every((value) => typeof value === 'string');
  const xAxisOptions = isTimeBased
    ? {
        type: 'datetime',
        labels: { style: { color: '#becfff' }, format: '{value:%b %e %H:%M}' },
        gridLineColor: 'rgba(255,255,255,0.06)',
      }
    : {
        categories: chartConfig.categories,
        labels: { style: { color: '#becfff' } },
        gridLineColor: 'rgba(255,255,255,0.06)',
      };

  const series = isTimeBased
    ? chartConfig.series.map((seriesItem) => ({
        ...seriesItem,
        data: seriesItem.data.map((pointValue, index) => [Date.parse(chartConfig.categories[index]), pointValue]),
      }))
    : chartConfig.series;

  const yAxisOptions = {
    title: { text: chartConfig.yAxisTitle || '' },
    labels: { style: { color: '#becfff' } },
    gridLineColor: 'rgba(255,255,255,0.06)',
  };
  if (containerId === 'chart-users') {
    yAxisOptions.min = 0;
  }

  Highcharts.chart(containerId, {
    chart: {
      backgroundColor: 'transparent',
      plotBackgroundColor: 'transparent',
      style: {
        fontFamily: 'Inter, sans-serif',
      },
      zoomType: 'x',
    },
    title: { text: null },
    credits: { enabled: false },
    legend: { itemStyle: { color: '#cbd9ff' } },
    xAxis: xAxisOptions,
    yAxis: yAxisOptions,
    series,
    tooltip: { shared: true, backgroundColor: 'rgba(8, 15, 28, 0.96)', borderColor: '#4aa5ff', style: { color: '#fff' }, xDateFormat: '%b %e %H:%M' },
    plotOptions: {
      series: { marker: { enabled: false }, lineWidth: 2 },
      column: { borderRadius: 4, borderWidth: 0 },
    },
    chartArea: { backgroundColor: 'transparent' },
    responsive: { rules: [{ condition: { maxWidth: 720 }, chartOptions: { legend: { enabled: false } } }] },
  });
}

function roundValue(value) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.round(value * 1000) / 1000;
}

function formatValue(value, label) {
  if (label === 'percent') {
    return `${roundValue(value).toFixed(2)}%`;
  }
  return Number.isFinite(value) ? roundValue(value) : 0;
}

function sizeLabel(value) {
  if (value >= 1024 ** 3) {
    return `${(value / 1024 ** 3).toFixed(3)} GB`;
  }
  return `${(value / 1024 ** 2).toFixed(3)} MB`;
}

function buildSeries(timeline, fieldName) {
  return timeline.map((entry) => roundValue(entry[fieldName] ?? 0));
}

function buildDiffSeries(timeline, fieldName) {
  return timeline.map((entry, index) => {
    if (index === 0) {
      return 0;
    }
    return (entry[fieldName] ?? 0) - (timeline[index - 1][fieldName] ?? 0);
  });
}

function formatMetricValue(key, value) {
  if (key === 'LikePercentage') {
    return `${roundValue(value).toFixed(2)}%`;
  }
  if (key === 'TotalSize') {
    return sizeLabel(value);
  }
  if (key === 'ErrorRate') {
    return `${roundValue(value).toFixed(4)}%`;
  }
  if (key === 'Created') {
    return value || '-';
  }
  return Number.isFinite(value) ? roundValue(value) : (value ?? 0);
}

const GAME_TABLE_FIELDS = [
  { key: 'Favourited', label: 'Favorites' },
  { key: 'VotesUp', label: 'Likes' },
  { key: 'VotesDown', label: 'Dislikes' },
  { key: 'LikePercentage', label: 'Like %' },
  { key: 'Created', label: 'Created' },
  { key: 'TotalSize', label: 'Size' },
  { key: 'ErrorRate', label: 'Error Rate' },
];

function getFieldLabel(key) {
  const field = GAME_TABLE_FIELDS.find((item) => item.key === key);
  return field ? field.label : key;
}

function buildGameTableRow(game, metricKey) {
  return `
    <tr class="game-table-row" data-title="${game.title.toLowerCase()}" data-org="${game.org.toLowerCase()}" data-players="${game.UsersNow}" data-metric="${game[metricKey] ?? ''}">
      <td>
        <a class="table-game-link" href="${game.file}">
          <img class="table-preview" src="${game.preview}" alt="${game.title} preview" />
          <div>
            <strong>${game.title}</strong>
            <span>${game.org}</span>
          </div>
        </a>
      </td>
      <td>${roundValue(game.UsersNow)}</td>
      <td>${formatMetricValue(metricKey, game[metricKey])}</td>
    </tr>
  `;
}

function renderGameTable(metricKey, sortKey, sortDescending) {
  const tableBody = document.getElementById('game-table-body');
  const metricHeader = document.getElementById('metric-header');
  if (!tableBody || !window.gameTableData) {
    return;
  }

  metricHeader.textContent = getFieldLabel(metricKey);

  const sortedData = [...window.gameTableData].sort((a, b) => {
    const left = a[sortKey];
    const right = b[sortKey];

    if (sortKey === 'Title' || sortKey === 'Created') {
      if ((left || '') < (right || '')) return sortDescending ? 1 : -1;
      if ((left || '') > (right || '')) return sortDescending ? -1 : 1;
      return 0;
    }

    return sortDescending ? (right - left) : (left - right);
  });

  tableBody.innerHTML = sortedData.map((game) => buildGameTableRow(game, metricKey)).join('');
}

function getSelectedMetric() {
  const metricSelect = document.getElementById('game-table-metric');
  return metricSelect ? metricSelect.value : 'Favourited';
}

function getSelectedSortKey() {
  const sortSelect = document.getElementById('game-table-sort');
  return sortSelect ? sortSelect.value : 'UsersNow';
}

function initGameTable() {
  if (!window.gameTableData) {
    return;
  }

  const metricSelect = document.getElementById('game-table-metric');
  const sortSelect = document.getElementById('game-table-sort');
  const searchInput = document.getElementById('game-search');
  let sortDescending = true;

  function refreshTable() {
    renderGameTable(getSelectedMetric(), getSelectedSortKey(), sortDescending);
    filterGameTable(searchInput ? searchInput.value : '');
  }

  if (metricSelect) {
    metricSelect.addEventListener('change', refreshTable);
  }

  if (sortSelect) {
    sortSelect.addEventListener('change', refreshTable);
  }

  const header = document.querySelector('.game-table thead');
  if (header) {
    header.addEventListener('click', (event) => {
      if (!event.target.closest('th')) return;
      const th = event.target.closest('th');
      const key = th.id === 'metric-header' ? getSelectedMetric() : th.textContent === 'Players' ? 'UsersNow' : 'Title';
      if (sortSelect) {
        sortSelect.value = key;
      }
      sortDescending = !sortDescending;
      refreshTable();
    });
  }

  refreshTable();
}

function filterGameTable(query) {
  const lowerQuery = query.trim().toLowerCase();
  const rows = Array.from(document.querySelectorAll('.game-table-row'));
  rows.forEach((row) => {
    const title = row.dataset.title;
    const org = row.dataset.org;
    row.style.display = title.includes(lowerQuery) || org.includes(lowerQuery) ? '' : 'none';
  });
}

function initSearch() {
  const searchInput = document.getElementById('game-search');
  const gameList = document.getElementById('game-list');
  if (!searchInput) {
    return;
  }

  searchInput.addEventListener('input', () => {
    const query = searchInput.value.trim().toLowerCase();
    if (window.gameTableData) {
      filterGameTable(query);
      return;
    }

    if (!gameList) {
      return;
    }

    const cards = Array.from(gameList.querySelectorAll('.game-search-card'));
    cards.forEach((card) => {
      const title = card.dataset.title.toLowerCase();
      const org = card.dataset.org.toLowerCase();
      card.style.display = title.includes(query) || org.includes(query) ? '' : 'none';
    });
  });
}

function createStatsCard(title, value) {
  const card = document.createElement('div');
  card.className = 'stats-card';
  card.innerHTML = `<h4>${title}</h4><p>${value}</p>`;
  return card;
}

function renderCards(latest) {
  const target = document.getElementById('stats-grid');
  if (!target) return;

  const stats = [
    ['Players', latest.UsersNow],
    ['Favorites', latest.Favourited],
    ['Collections', latest.Collections],
    ['Votes Up', latest.VotesUp],
    ['Votes Down', latest.VotesDown],
    ['Like %', `${latest.LikePercentage.toFixed(2)}%`],
    ['Total Users', latest.TotalUsers],
    ['Total Hours', (latest.TotalSeconds / 3600).toFixed(3)],
    ['Visits', latest.TotalSessions],
    ['File Count', latest.FileCount],
    ['Total Size', sizeLabel(latest.TotalSize)],
    ['Error Rate', `${latest.ErrorRate.toFixed(4)}%`],
  ];

  if (window.pageData && window.pageData.kind === 'org') {
    const collectionIndex = stats.findIndex(([label]) => label === 'Collections');
    if (collectionIndex !== -1) {
      stats[collectionIndex] = ['Games', latest.GameCount ?? 0];
    }
  }

  stats.forEach(([label, value]) => {
    target.appendChild(createStatsCard(label, value));
  });
}

function renderHomeCards(stats) {
  const hero = document.querySelector('.hero-summary');
  if (!hero || !stats) return;
  hero.innerHTML = '';

  const cardEntries = [
    ['Games tracked', stats.games],
    ['Players tracked', stats.players],
    ['Organizations', stats.orgs],
    ['Favorites', stats.favorites],
    ['Collections', stats.collections],
    ['Latest update', stats.lastUpdated],
  ];

  cardEntries.forEach(([label, value]) => {
    const card = document.createElement('div');
    card.className = 'hero-summary-card';
    card.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    hero.appendChild(card);
  });
}

function renderHomePage() {
  if (!window.homePageData) {
    return;
  }

  renderHomeCards(window.homePageData.stats);

  const timeline = window.homePageData.timeline || [];
  const categories = timeline.map((entry) => entry.Time || '');
  const players = timeline.map((entry) => entry.Players || 0);
  const games = timeline.map((entry) => entry.Games || 0);

  renderChart('chart-home', {
    categories,
    series: [
      { name: 'Total Players', data: players, color: '#5db4ff' },
      { name: 'Tracked Games', data: games, color: '#78beff' },
    ],
    yAxisTitle: 'Count',
  });
}

function initSite() {
  initGameTable();

  if (window.pageData) {
    renderCards(window.pageData.latest);

    const timeline = window.pageData.timeline || [];
    const categories = timeline.map((entry) => entry.Time || '');

    renderChart('chart-users', {
      categories,
      series: [{ name: 'Users', data: buildSeries(timeline, 'UsersNow'), color: '#5db4ff' }],
      yAxisTitle: 'Players',
    });

    renderChart('chart-favourites', {
      categories,
      series: [{ name: 'Favorites', data: buildSeries(timeline, 'Favourited'), color: '#5db4ff' }],
      yAxisTitle: 'Favorites',
    });

    renderChart('chart-favourites-gain', {
      categories,
      series: [{ name: 'Favorites Gain', data: buildDiffSeries(timeline, 'Favourited'), type: 'column', color: '#2889ff' }],
      yAxisTitle: 'Change',
    });

    renderChart('chart-collections', {
      categories,
      series: [{ name: 'Collections', data: buildSeries(timeline, 'Collections'), color: '#5db4ff' }],
      yAxisTitle: 'Collections',
    });

    renderChart('chart-votes', {
      categories,
      series: [
        { name: 'Votes Up', data: buildSeries(timeline, 'VotesUp'), color: '#50c9ba' },
        { name: 'Votes Down', data: buildSeries(timeline, 'VotesDown'), color: '#7f98ff' },
      ],
      yAxisTitle: 'Votes',
    });

    renderChart('chart-vote-change', {
      categories,
      series: [
        { name: 'Votes Up Change', data: buildDiffSeries(timeline, 'VotesUp'), type: 'column', color: '#50c9ba' },
        { name: 'Votes Down Change', data: buildDiffSeries(timeline, 'VotesDown'), type: 'column', color: '#7f98ff' },
      ],
      yAxisTitle: 'Delta',
    });

    renderChart('chart-like-percent', {
      categories,
      series: [{ name: 'Like %', data: buildSeries(timeline, 'LikePercentage'), color: '#8abdff' }],
      yAxisTitle: 'Percent',
    });

    renderChart('chart-total-users', {
      categories,
      series: [{ name: 'Total Users', data: buildSeries(timeline, 'TotalUsers'), color: '#5db4ff' }],
      yAxisTitle: 'Users',
    });

    renderChart('chart-total-hours', {
      categories,
      series: [{ name: 'Total Hours', data: timeline.map((entry) => roundValue((entry.TotalSeconds || 0) / 3600)), color: '#5db4ff' }],
      yAxisTitle: 'Hours',
    });

    renderChart('chart-visits', {
      categories,
      series: [{ name: 'Visits', data: buildSeries(timeline, 'TotalSessions'), color: '#5db4ff' }],
      yAxisTitle: 'Visits',
    });

    renderChart('chart-visits-change', {
      categories,
      series: [{ name: 'Visits Change', data: buildDiffSeries(timeline, 'TotalSessions'), type: 'column', color: '#4aa5ff' }],
      yAxisTitle: 'Delta',
    });

    renderChart('chart-file-count', {
      categories,
      series: [{ name: 'File Count', data: buildSeries(timeline, 'FileCount'), color: '#5db4ff' }],
      yAxisTitle: 'Files',
    });

    renderChart('chart-total-size', {
      categories,
      series: [
        {
          name: 'Total Size (MB)',
          data: timeline.map((entry) => roundValue((entry.TotalSize || 0) / 1024 / 1024)),
          color: '#5db4ff',
        },
      ],
      yAxisTitle: 'MB',
    });

    renderChart('chart-error-rate', {
      categories,
      series: [{ name: 'Error Rate', data: buildSeries(timeline, 'ErrorRate'), color: '#ff7ed0' }],
      yAxisTitle: 'Percent',
    });
  }
}

function initTabs() {
  const buttons = Array.from(document.querySelectorAll('.tab-button'));
  const panels = Array.from(document.querySelectorAll('.tab-panel'));
  if (!buttons.length || !panels.length) {
    return;
  }

  function showTab(tabId) {
    panels.forEach((panel) => {
      panel.classList.toggle('tab-hidden', panel.id !== tabId);
    });
    buttons.forEach((button) => {
      button.classList.toggle('tab-active', button.dataset.tab === tabId);
    });
  }

  buttons.forEach((button) => {
    button.addEventListener('click', () => showTab(button.dataset.tab));
  });

  showTab('games-tab');
}

function initAddOrgPage() {
  const form = document.getElementById('add-org-form');
  const message = document.getElementById('add-org-message');
  if (!form || !message) {
    return;
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const orgField = document.getElementById('org-name');
    if (!orgField) {
      return;
    }

    const org = orgField.value.trim();
    if (!org) {
      message.textContent = 'Enter an organization name.';
      return;
    }

    message.textContent = 'Adding org…';
    message.style.color = '#b8d5ff';

    try {
      const response = await fetch('/api/add_org', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ org }),
      });

      if (!response.ok) {
        const result = await response.json();
        message.textContent = result.error || 'Failed to add org.';
        message.style.color = '#ff8fab';
        return;
      }

      message.textContent = 'Org added. Reloading…';
      message.style.color = '#90d2ff';
      setTimeout(() => {
        window.location.reload();
      }, 500);
    } catch (error) {
      message.textContent = 'Unable to connect to the server.';
      message.style.color = '#ff8fab';
    }
  });
}

window.addEventListener('DOMContentLoaded', () => {
  initSite();
  initSearch();
  initTabs();
  if (window.addOrgPage) {
    initAddOrgPage();
  }
});
