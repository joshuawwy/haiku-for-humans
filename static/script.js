// Haiku for Humans — frontend logic (two-column layout)

const topFeed = document.getElementById('top-feed');
const topEmpty = document.getElementById('top-empty');
const newFeed = document.getElementById('new-feed');
const loader = document.getElementById('loader');
const emptyState = document.getElementById('empty-state');

let currentPage = 1;
let hasMore = true;
let loading = false;

// Track votes in localStorage
function getVoted() {
  try {
    return JSON.parse(localStorage.getItem('haiku-votes') || '{}');
  } catch {
    return {};
  }
}

function markVoted(id) {
  const voted = getVoted();
  voted[id] = true;
  localStorage.setItem('haiku-votes', JSON.stringify(voted));
}

function isVoted(id) {
  return !!getVoted()[id];
}

// Relative time formatting
function timeAgo(dateStr) {
  const now = new Date();
  const date = new Date(dateStr);
  const seconds = Math.floor((now - date) / 1000);

  if (seconds < 60) return 'just now';
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    return m + 'm ago';
  }
  if (seconds < 86400) {
    const h = Math.floor(seconds / 3600);
    return h + 'h ago';
  }
  if (seconds < 172800) return 'yesterday';
  if (seconds < 604800) {
    const d = Math.floor(seconds / 86400);
    return d + 'd ago';
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Build a haiku card element using safe DOM methods
function createCard(haiku, index) {
  const card = document.createElement('article');
  card.className = 'haiku-card';
  card.dataset.index = Math.min(index, 9);

  const voted = isVoted(haiku.id);

  // Haiku text
  const haikuText = document.createElement('p');
  haikuText.className = 'haiku-text';
  haikuText.textContent = haiku.text;

  // Meta container
  const meta = document.createElement('div');
  meta.className = 'haiku-meta';

  const author = document.createElement('span');
  author.className = 'haiku-author';
  author.textContent = '@' + haiku.author;

  const time = document.createElement('span');
  time.className = 'haiku-time';
  time.textContent = timeAgo(haiku.created_at);

  // Upvote button
  const btn = document.createElement('button');
  btn.className = 'upvote-btn' + (voted ? ' voted' : '');
  btn.dataset.id = haiku.id;
  btn.setAttribute('aria-label', 'Upvote this haiku');
  btn.setAttribute('aria-pressed', voted ? 'true' : 'false');

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z');
  svg.appendChild(path);

  const count = document.createElement('span');
  count.className = 'vote-count';
  count.textContent = haiku.votes;

  btn.appendChild(svg);
  btn.appendChild(count);
  btn.addEventListener('click', function() { handleUpvote(btn, haiku.id); });

  meta.appendChild(author);
  meta.appendChild(time);
  meta.appendChild(btn);

  card.appendChild(haikuText);
  card.appendChild(meta);

  return card;
}

// Handle upvote click
async function handleUpvote(btn, id) {
  if (isVoted(id)) return;

  btn.classList.add('voted', 'pop');
  btn.setAttribute('aria-pressed', 'true');

  setTimeout(function() { btn.classList.remove('pop'); }, 300);

  try {
    const res = await fetch('/api/haikus/' + id + '/upvote', { method: 'POST' });
    const data = await res.json();
    btn.querySelector('.vote-count').textContent = data.votes;
    markVoted(id);
  } catch {
    btn.classList.remove('voted');
    btn.setAttribute('aria-pressed', 'false');
  }
}

// Load top-voted haikus (left column)
async function loadTopHaikus() {
  try {
    const res = await fetch('/api/haikus/top');
    const data = await res.json();

    if (data.haikus.length === 0) {
      topEmpty.hidden = false;
      return;
    }

    topEmpty.hidden = true;
    topFeed.replaceChildren(); // Clear and rebuild
    const fragment = document.createDocumentFragment();
    data.haikus.forEach(function(haiku, i) {
      fragment.appendChild(createCard(haiku, i));
    });
    topFeed.appendChild(fragment);
  } catch (err) {
    console.error('Failed to load top haikus:', err);
  }
}

// Load new haikus (right column, paginated)
async function loadNewHaikus() {
  if (loading || !hasMore) return;
  loading = true;
  loader.hidden = false;

  try {
    const res = await fetch('/api/haikus?page=' + currentPage);
    const data = await res.json();

    if (currentPage === 1 && data.haikus.length === 0) {
      emptyState.hidden = false;
      loader.hidden = true;
      loading = false;
      return;
    }

    const fragment = document.createDocumentFragment();
    data.haikus.forEach(function(haiku, i) {
      fragment.appendChild(createCard(haiku, i));
    });
    newFeed.appendChild(fragment);

    hasMore = data.has_more;
    currentPage++;
  } catch (err) {
    console.error('Failed to load new haikus:', err);
  }

  loader.hidden = true;
  loading = false;
}

// Infinite scroll for new column
const observer = new IntersectionObserver(
  function(entries) {
    if (entries[0].isIntersecting && hasMore && !loading) {
      loadNewHaikus();
    }
  },
  { rootMargin: '200px' }
);

observer.observe(loader);

// Initial load — both columns in parallel
loadTopHaikus();
loadNewHaikus();
