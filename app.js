const storiesEl = document.querySelector('#stories');
const statusEl = document.querySelector('#status');
const template = document.querySelector('#storyTemplate');
const search = document.querySelector('#searchInput');
const refreshButton = document.querySelector('#refreshButton');
let stories = [];
let activeCategory = 'All';
let wellnessRankings = {};
let activeRanking = 'continents';

const displayDate = (value) => {
  const date = new Date(value);
  return Number.isNaN(date) ? 'Latest' : new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date);
};

function render() {
  const term = search.value.trim().toLowerCase();
  const view = stories.filter((story) => (activeCategory === 'All' || story.category === activeCategory)
    && (!term || `${story.title} ${story.summary} ${story.source}`.toLowerCase().includes(term)));
  storiesEl.replaceChildren();
  const categories = activeCategory === 'All' ? ['Science', 'Innovation', 'Business', 'Culture'] : [activeCategory];
  categories.forEach((category) => {
    const sectionStories = view.filter((story) => story.category === category);
    if (!sectionStories.length) return;
    const section = document.createElement('section');
    section.className = 'carousel-section';
    const heading = document.createElement('div');
    heading.className = 'carousel-heading';
    heading.innerHTML = `<p class="eyebrow">${category} DESK</p><div><button class="carousel-control" type="button" aria-label="Previous ${category} stories">←</button><button class="carousel-control" type="button" aria-label="Next ${category} stories">→</button></div>`;
    const rail = document.createElement('div');
    rail.className = 'story-rail';
    sectionStories.forEach((story) => {
      const node = template.content.cloneNode(true);
      const image = node.querySelector('.story-image');
      image.src = story.image || 'assets/sleep-wellness-feature.png';
      image.alt = story.title ? `Featured image for ${story.title}` : 'Sleep wellness editorial image';
      image.addEventListener('error', () => { image.src = 'assets/sleep-wellness-feature.png'; }, { once: true });
      node.querySelector('.category').textContent = story.category;
      node.querySelector('time').textContent = displayDate(story.published);
      node.querySelector('h2').textContent = story.title;
      node.querySelector('.summary').textContent = story.summary || 'Open the original source for the full update.';
      node.querySelector('.source').textContent = story.source;
      const link = node.querySelector('a');
      link.href = story.link;
      link.setAttribute('aria-label', `Read ${story.title}`);
      rail.append(node);
    });
    heading.querySelectorAll('.carousel-control').forEach((button, index) => button.addEventListener('click', () => {
      rail.scrollBy({ left: (index ? 1 : -1) * Math.round(rail.clientWidth * 0.82), behavior: 'smooth' });
    }));
    section.append(heading, rail);
    storiesEl.append(section);
  });
  statusEl.hidden = view.length > 0;
  if (!view.length) {
    statusEl.hidden = false;
    statusEl.textContent = 'No stories match this filter yet.';
  }
}

function updateFeatured(items) {
  const story = items[0];
  if (!story) return;
  document.querySelector('#featuredCategory').textContent = story.category.toUpperCase();
  document.querySelector('#featuredTitle').textContent = story.title;
  document.querySelector('#featuredSummary').textContent = story.summary || 'Open the source for the full briefing.';
  const link = document.querySelector('#featuredLink');
  link.href = story.link;
  link.setAttribute('aria-label', `Open featured story: ${story.title}`);
}

function updateStats(data) {
  document.querySelector('#storyCount').textContent = data.stories.length;
  document.querySelector('#sourceCount').textContent = data.sources || '-';
  const cutoff = Date.now() - 48 * 60 * 60 * 1000;
  document.querySelector('#freshCount').textContent = data.stories.filter((item) => new Date(item.published).getTime() > cutoff).length;
  document.querySelector('#lastUpdated').textContent = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', weekday: 'short' }).format(new Date());
}

function scoreSignal(score) {
  if (score >= 80) return 'Strong';
  if (score >= 70) return 'Steady';
  return 'Watch';
}

function renderWellness() {
  const rows = wellnessRankings[activeRanking] || [];
  const body = document.querySelector('#rankingBody');
  const labels = { continents: 'Continent', countries: 'Country', cities: 'City' };
  document.querySelector('#rankingPlace').textContent = labels[activeRanking];
  body.replaceChildren();
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="4">The ranking service is unavailable.</td></tr>';
    return;
  }
  rows.forEach((place, index) => {
    const signal = scoreSignal(place.score);
    const row = document.createElement('tr');
    row.innerHTML = `<td>${index + 1}</td><th scope="row">${place.name}</th><td><span class="score">${place.score}</span><span class="score-bar"><i style="width:${place.score}%"></i></span></td><td><span class="signal ${signal.toLowerCase()}">${signal}</span></td>`;
    body.append(row);
  });
}

async function loadWellness() {
  try {
    const response = await fetch('/api/wellness', { cache: 'no-store' });
    if (!response.ok) throw new Error('Wellness service is not responding');
    const data = await response.json();
    wellnessRankings = data.rankings || {};
    document.querySelector('#wellnessUpdated').textContent = `LIVE · ${new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', weekday: 'short' }).format(new Date(data.updated_at || Date.now()))}`;
    renderWellness();
  } catch (error) {
    document.querySelector('#wellnessUpdated').textContent = 'INDEX OFFLINE';
    renderWellness();
  }
}

async function loadNews() {
  refreshButton.classList.add('loading');
  refreshButton.disabled = true;
  statusEl.hidden = false;
  statusEl.classList.remove('error');
  statusEl.textContent = 'Scanning the public news wires...';
  try {
    const response = await fetch('/api/news', { cache: 'no-store' });
    if (!response.ok) throw new Error('News service is not responding');
    const data = await response.json();
    stories = data.stories || [];
    if (!stories.length) throw new Error('No matching stories arrived from the feeds');
    updateStats(data);
    updateFeatured(stories);
    render();
  } catch (error) {
    statusEl.hidden = false;
    statusEl.classList.add('error');
    statusEl.innerHTML = 'Could not reach the local news service. Start it with <code>python server.py</code>, then open <code>http://localhost:8000</code>.';
  } finally {
    refreshButton.classList.remove('loading');
    refreshButton.disabled = false;
  }
}

document.querySelectorAll('[data-category]').forEach((button) => button.addEventListener('click', () => {
  activeCategory = button.dataset.category;
  document.querySelectorAll('[data-category]').forEach((item) => item.classList.toggle('active', item === button));
  render();
}));
search.addEventListener('input', render);
refreshButton.addEventListener('click', () => {
  loadNews();
  loadWellness();
});
document.querySelectorAll('[data-ranking]').forEach((button) => button.addEventListener('click', () => {
  activeRanking = button.dataset.ranking;
  document.querySelectorAll('[data-ranking]').forEach((item) => {
    const active = item === button;
    item.classList.toggle('active', active);
    item.setAttribute('aria-selected', active);
  });
  renderWellness();
}));
loadNews();
loadWellness();
