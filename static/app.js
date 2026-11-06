// ==========================================================================
// 小帆船 · 鞋样送审系统 (Navigare PSDweb 2.2 Pro)
// UI/UX Design System Inspired by "秋知设计助手"
// ==========================================================================

const state = {
  groups: [],                // Array of TaskGroupItem: [{ id, name, created_at, tasks: [...] }]
  active_group_id: null,
  active_task_id: null,
  selected_shoe_id: null,
  products_db: [],           // Array of ProductItem (Multi-Color Supported)
  logos_pool: [],
  base_fit_scale: 0.33,
  custom_zoom_ratio: 1.0,
  stage_scale: 0.33,
  meta_options: {},
  pending_delete_group_id: null,
  form_colors_data: [],      // Temporary color rows inside product editor form
  template_config: {
    title: "臻兴科技开发样品单",
    logo_url: "/static/assets/logos/logo_square_boat.png",
    logo_filename: "logos/logo_square_boat.png",
    is_custom: false
  },
  is_editing_template: false,
  replacing_shoe_id: null,
  replacing_logo_id: null,
  current_typo_target: null,
  logo_category: "all",
  logo_search_query: ""
};

const STAGE_W = 3508;
const STAGE_H = 2480;

const DEFAULT_COLOR_PALETTE = [
  "黑色", "酒红", "粉色", "米白", "卡其", "深蓝", 
  "深灰", "浅灰", "墨绿", "棕色", "奶茶", "焦糖", 
  "大红", "藏青", "银白"
];

// DOM References
const stage = document.getElementById("sheet-stage");
const stageShoesLayer = document.getElementById("stage-shoes-layer");
const sidebarTasksList = document.getElementById("sidebar-tasks-list");
const groupSelectEl = document.getElementById("group-select");
const loadingModal = document.getElementById("loading-modal");
const loadingText = document.getElementById("loading-text");
const zoomLevelText = document.getElementById("zoom-level-text");

// Modals
const modalProductLib = document.getElementById("modal-product-library");
const modalAiParser = document.getElementById("modal-ai-parser");
const modalRenameGroup = document.getElementById("modal-rename-group");
const modalDeleteGroup = document.getElementById("modal-delete-group-confirm");

document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  setupStageScale();
  window.addEventListener("resize", () => {
    setupStageScale();
    updateStageUI();
  });

  await loadInitialMeta();
  await loadGroupsFromServer();
  await loadProductLibrary();
  setupEventListeners();
  setupZoomControls();
  renderGroupSelect();
  renderTasksNav();
  updateStageUI();
  renderShoeListCards();

  if (window.location.search.includes("open=library")) {
    openProductLibraryModal();
  } else if (window.location.search.includes("open=ai")) {
    openAiParserModal();
  }
});

// --- Theme Management (秋知助手: 浅色 ☀️ / 深色 🌙 双模) ---
function initTheme() {
  const saved = localStorage.getItem("navigare_theme") || "light";
  applyTheme(saved);

  const toggleBtn = document.getElementById("btn-theme-toggle");
  if (toggleBtn) {
    toggleBtn.onclick = () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const next = current === "light" ? "dark" : "light";
      applyTheme(next);
      localStorage.setItem("navigare_theme", next);
    };
  }
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const icon = document.getElementById("theme-icon");
  if (icon) {
    icon.textContent = theme === "dark" ? "☀️" : "🌙";
  }
}

// --- Strict Equal-Ratio 3508:2480 Canvas Viewport Scaling ---
function setupStageScale() {
  const viewport = document.getElementById("canvas-viewport");
  const scaleContainer = document.getElementById("stage-scale-container");
  if (!viewport || !stage || !scaleContainer) return;

  const padX = 80;
  const padY = 100;
  const availW = Math.max(300, viewport.clientWidth - padX);
  const availH = Math.max(200, viewport.clientHeight - padY);
  
  const scaleW = availW / STAGE_W;
  const scaleH = availH / STAGE_H;
  state.base_fit_scale = Math.min(scaleW, scaleH);

  let finalScale = state.base_fit_scale;
  if (state.zoom_mode === "100") {
    finalScale = 1.0;
  } else if (state.zoom_mode === "custom") {
    finalScale = state.custom_zoom_ratio || state.base_fit_scale;
  } else {
    // "fit" (default)
    state.zoom_mode = "fit";
    finalScale = state.base_fit_scale;
  }
  state.stage_scale = finalScale;
  
  const stageW = Math.round(STAGE_W * finalScale);
  const stageH = Math.round(STAGE_H * finalScale);
  
  scaleContainer.style.width = `${stageW}px`;
  scaleContainer.style.height = `${stageH}px`;
  stage.style.width = `${STAGE_W}px`;
  stage.style.height = `${STAGE_H}px`;
  stage.style.transform = `scale(${finalScale})`;
  stage.style.transformOrigin = "top left";

  if (zoomLevelText) {
    if (state.zoom_mode === "fit") {
      zoomLevelText.textContent = `适应 (${Math.round(finalScale * 100)}%)`;
    } else {
      zoomLevelText.textContent = `${Math.round(finalScale * 100)}%`;
    }
  }
}

function setupZoomControls() {
  const btnIn = document.getElementById("btn-zoom-in");
  const btnOut = document.getElementById("btn-zoom-out");
  const btn100 = document.getElementById("btn-zoom-100");
  const btnFit = document.getElementById("btn-zoom-fit");

  if (btnIn) {
    btnIn.onclick = () => {
      state.zoom_mode = "custom";
      state.custom_zoom_ratio = Math.min(3.0, (state.stage_scale || 1.0) * 1.2);
      setupStageScale();
      updateStageUI();
    };
  }
  if (btnOut) {
    btnOut.onclick = () => {
      state.zoom_mode = "custom";
      state.custom_zoom_ratio = Math.max(0.15, (state.stage_scale || 1.0) / 1.2);
      setupStageScale();
      updateStageUI();
    };
  }
  if (btn100) {
    btn100.onclick = () => {
      state.zoom_mode = "100";
      state.custom_zoom_ratio = 1.0;
      setupStageScale();
      updateStageUI();
    };
  }
  if (btnFit) {
    btnFit.onclick = () => {
      state.zoom_mode = "fit";
      state.custom_zoom_ratio = state.base_fit_scale;
      setupStageScale();
      updateStageUI();
    };
  }
}

function toStagePx(val) {
  return Math.round(val);
}

// Helpers
function getActiveGroup() {
  return state.groups.find(g => g.id === state.active_group_id) || state.groups[0];
}

function getActiveTask() {
  const group = getActiveGroup();
  if (!group || !group.tasks || group.tasks.length === 0) return null;
  return group.tasks.find(t => t.id === state.active_task_id) || group.tasks[0];
}

// --- Initial Metadata ---
async function loadInitialMeta() {
  try {
    const res = await fetch("/api/initial-data");
    const data = await res.json();
    state.meta_options = data;
    state.logos_pool = data.logos;
    if (data.template_config) {
      state.template_config = data.template_config;
    }
    
    if (data.lan_url) {
      document.getElementById("lan-url-text").textContent = data.lan_url;
    }
    
    renderLogoPool(data.logos);
    renderTableVectorLines();
    renderTableTexts();
  } catch (err) {
    console.error(err);
  }
}

// --- Task Groups (送审批次标签) CRUD & 二次确认删除 ---

async function loadGroupsFromServer() {
  try {
    const res = await fetch("/api/groups");
    const data = await res.json();
    if (data.status === "success" && data.groups && data.groups.length > 0) {
      state.groups = data.groups;
      state.active_group_id = state.groups[0].id;
      if (state.groups[0].tasks && state.groups[0].tasks.length > 0) {
        state.active_task_id = state.groups[0].tasks[0].id;
        loadTaskIntoInputs(state.groups[0].tasks[0]);
      }
    } else {
      createDefaultInitialGroup();
    }
  } catch (err) {
    console.error(err);
    createDefaultInitialGroup();
  }
}

function createDefaultInitialGroup() {
  const today = state.meta_options.material_code || new Date().toISOString().slice(0, 10).replace(/-/g, ".");
  const defaultTask = {
    id: `task_${Date.now()}`,
    name: "款式 206209",
    sku: "206209",
    material_code: today,
    size: "36",
    category: "单鞋",
    season: "四季鞋",
    craft: "冷粘",
    fabrics: "牛反绒+沙丁布",
    soles: "橡胶大底",
    shoes: []
  };

  const defaultGroup = {
    id: "group_default",
    name: "11.06 送审批次 (默认)",
    created_at: new Date().toISOString(),
    tasks: [defaultTask]
  };

  state.groups = [defaultGroup];
  state.active_group_id = defaultGroup.id;
  state.active_task_id = defaultTask.id;
  loadTaskIntoInputs(defaultTask);
  syncGroupsToServer();
}

function renderGroupSelect() {
  groupSelectEl.innerHTML = "";
  state.groups.forEach(group => {
    const opt = document.createElement("option");
    opt.value = group.id;
    opt.textContent = `${group.name} (${group.tasks?.length || 0}款)`;
    if (group.id === state.active_group_id) {
      opt.selected = true;
    }
    groupSelectEl.appendChild(opt);
  });
  
  const activeGrp = getActiveGroup();
  if (activeGrp) {
    document.getElementById("sidebar-batch-name").textContent = activeGrp.name;
    document.getElementById("sidebar-tasks-count").textContent = `${activeGrp.tasks?.length || 0} 款`;
  }
}

function switchGroup(groupId) {
  state.active_group_id = groupId;
  const group = getActiveGroup();
  if (!group.tasks || group.tasks.length === 0) {
    createNewTask();
  } else {
    state.active_task_id = group.tasks[0].id;
    loadTaskIntoInputs(group.tasks[0]);
  }
  renderGroupSelect();
  renderTasksNav();
  updateStageUI();
  renderShoeListCards();
}

async function handleCreateGroup() {
  const name = prompt("请输入新建任务批次标签名称：\n例如：胡生-11.07送审批次", `新送审批次 ${state.groups.length + 1}`);
  if (!name || !name.trim()) return;

  const today = state.meta_options.material_code || new Date().toISOString().slice(0, 10).replace(/-/g, ".");
  const newGroupId = `group_${Date.now()}`;
  const initialTask = {
    id: `task_${Date.now()}`,
    name: "新送审款式 1",
    sku: "",
    material_code: today,
    size: "36",
    category: "单鞋",
    season: "四季鞋",
    craft: "冷粘",
    fabrics: "牛反绒",
    soles: "橡胶大底",
    shoes: []
  };

  const newGroup = {
    id: newGroupId,
    name: name.trim(),
    created_at: new Date().toISOString(),
    tasks: [initialTask]
  };

  showLoading("正在创建任务标签...");
  try {
    const res = await fetch("/api/groups", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newGroup)
    });
    const data = await res.json();
    if (data.status === "success") {
      state.groups.push(newGroup);
      state.active_group_id = newGroup.id;
      state.active_task_id = initialTask.id;
      loadTaskIntoInputs(initialTask);
      renderGroupSelect();
      renderTasksNav();
      updateStageUI();
      renderShoeListCards();
      showToast(`✨ 标签【${name.trim()}】已创建成功！`);
    }
  } catch (err) {
    alert("创建失败: " + err.message);
  } finally {
    hideLoading();
  }
}

function handleOpenRenameGroupModal() {
  const group = getActiveGroup();
  document.getElementById("input-new-group-name").value = group.name;
  modalRenameGroup.classList.add("show");
}

async function handleConfirmRenameGroup() {
  const newName = document.getElementById("input-new-group-name").value.trim();
  if (!newName) {
    alert("标签名称不能为空！");
    return;
  }
  const group = getActiveGroup();
  group.name = newName;

  showLoading("正在修改标签名称...");
  try {
    await fetch(`/api/groups/${group.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(group)
    });
    modalRenameGroup.classList.remove("show");
    renderGroupSelect();
    showToast(`✏️ 标签已改名为：${newName}`);
  } catch (err) {
    alert("修改失败: " + err.message);
  } finally {
    hideLoading();
  }
}

// CRITICAL USER RULE: "任务标签可以删除，要有二次确认"
function handleOpenDeleteGroupModal() {
  if (state.groups.length <= 1) {
    alert("⚠️ 系统至少需要保留一个任务标签！无法删除最后一个标签。");
    return;
  }
  const group = getActiveGroup();
  state.pending_delete_group_id = group.id;
  document.getElementById("delete-target-group-name").textContent = `【${group.name}】（内含 ${group.tasks?.length || 0} 个款式任务）`;
  modalDeleteGroup.classList.add("show");
}

async function handleConfirmDeleteGroup() {
  const targetId = state.pending_delete_group_id;
  if (!targetId) return;

  showLoading("正在执行二次确认删除...");
  try {
    const res = await fetch(`/api/groups/${targetId}`, {
      method: "DELETE"
    });
    const data = await res.json();
    if (data.status === "success") {
      state.groups = state.groups.filter(g => g.id !== targetId);
      state.active_group_id = state.groups[0].id;
      const nextGroup = getActiveGroup();
      if (!nextGroup.tasks || nextGroup.tasks.length === 0) {
        createNewTask();
      } else {
        state.active_task_id = nextGroup.tasks[0].id;
        loadTaskIntoInputs(nextGroup.tasks[0]);
      }
      modalDeleteGroup.classList.remove("show");
      state.pending_delete_group_id = null;
      renderGroupSelect();
      renderTasksNav();
      updateStageUI();
      renderShoeListCards();
      showToast("🗑️ 任务标签已成功删除。");
    }
  } catch (err) {
    alert("删除失败: " + err.message);
  } finally {
    hideLoading();
  }
}

let syncTimer = null;
function syncGroupsToServer() {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(async () => {
    try {
      await fetch("/api/groups/save-all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.groups)
      });
    } catch (e) {
      console.warn("Auto-sync groups error:", e);
    }
  }, 1000);
}

// --- Tasks Management (Inside Active Group, Rendered on Left Sidebar) ---

function createNewTask() {
  const group = getActiveGroup();
  const count = (group.tasks?.length || 0) + 1;
  const today = state.meta_options.material_code || new Date().toISOString().slice(0, 10).replace(/-/g, ".");
  
  const newTask = {
    id: `task_${Date.now()}_${count}`,
    name: `新送审款式 ${count}`,
    sku: `2062${count > 9 ? count : '0' + count}`,
    material_code: today,
    size: "36",
    category: "单鞋",
    season: "四季鞋",
    craft: "冷粘",
    fabrics: "牛反绒",
    soles: "橡胶大底",
    shoes: []
  };

  if (!group.tasks) group.tasks = [];
  group.tasks.push(newTask);
  state.active_task_id = newTask.id;
  loadTaskIntoInputs(newTask);
  renderGroupSelect();
  renderTasksNav();
  updateStageUI();
  renderShoeListCards();
  syncGroupsToServer();
  showToast(`➕ 已添加款式：${newTask.name}`);
}

function switchTask(taskId) {
  state.active_task_id = taskId;
  const task = getActiveTask();
  if (task) {
    normalizeTaskShoes(task);
    state.selected_shoe_id = task.shoes[0]?.id || null;
    loadTaskIntoInputs(task);
    renderTasksNav();
    updateStageUI();
    renderShoeListCards();
  }
}

function deleteTask(taskId, e) {
  e.stopPropagation();
  const group = getActiveGroup();
  if (group.tasks.length <= 1) {
    alert("当前批次标签下至少保留 1 个款式任务！");
    return;
  }
  if (!confirm("确定删除该款式任务吗？")) return;
  group.tasks = group.tasks.filter(t => t.id !== taskId);
  if (state.active_task_id === taskId) {
    state.active_task_id = group.tasks[0].id;
  }
  switchTask(state.active_task_id);
  renderGroupSelect();
  syncGroupsToServer();
}

function normalizeTaskShoes(task) {
  if (!task || !task.shoes) return;
  task.shoes.forEach(s => {
    if (!s.raw_url && s.raw_filename) s.raw_url = `/static/uploads/${s.raw_filename}`;
    if (!s.cutout_url && s.cutout_filename) s.cutout_url = `/static/uploads/${s.cutout_filename}`;
    if (!s.cutout_url && s.raw_url) s.cutout_url = s.raw_url;
    if (!s.width) s.width = 800;
    if (!s.height) s.height = 500;
  });
}

function loadTaskIntoInputs(task) {
  if (!task) return;
  normalizeTaskShoes(task);
  document.getElementById("header-task-name").textContent = task.name;
  document.getElementById("input-sku").value = task.sku;
  document.getElementById("input-material-code").value = task.material_code;
  document.getElementById("input-size").value = task.size;
  document.getElementById("input-fabrics").value = task.fabrics;
  document.getElementById("input-soles").value = task.soles;

  // Render Pills
  renderPills("pill-category", state.meta_options.category_options || ["单鞋", "老爹鞋", "板鞋", "休闲鞋", "德训鞋", "马丁靴"], task.category, (v) => {
    task.category = v;
    updateStageUI();
    syncGroupsToServer();
  });
  renderPills("pill-season", state.meta_options.season_options || ["四季鞋", "春单", "秋单", "棉鞋", "凉鞋"], task.season, (v) => {
    task.season = v;
    updateStageUI();
    syncGroupsToServer();
  });
  renderPills("pill-craft", state.meta_options.craft_options || ["冷粘", "硫化", "注塑"], task.craft, (v) => {
    task.craft = v;
    updateStageUI();
    syncGroupsToServer();
  });

  // Render Tags
  renderTags("tags-fabric", state.meta_options.fabric_presets || ["牛反绒", "猪巴+沙丁布", "反绒皮+网布", "超纤皮"], (v) => {
    document.getElementById("input-fabrics").value = v;
    task.fabrics = v;
    updateStageUI();
    syncGroupsToServer();
  });
  renderTags("tags-sole", state.meta_options.sole_presets || ["橡胶大底", "MD大底", "橡胶+EVA", "发泡大底"], (v) => {
    document.getElementById("input-soles").value = v;
    task.soles = v;
    updateStageUI();
    syncGroupsToServer();
  });
}

// Render Tasks List inside Left Sidebar
function renderTasksNav() {
  const group = getActiveGroup();
  sidebarTasksList.innerHTML = "";
  if (!group || !group.tasks) return;

  document.getElementById("sidebar-tasks-count").textContent = `${group.tasks.length} 款`;

  group.tasks.forEach((task) => {
    const isActive = task.id === state.active_task_id;
    const card = document.createElement("div");
    card.className = `sidebar-task-card ${isActive ? "active" : ""}`;
    card.onclick = () => switchTask(task.id);

    const uncutCount = task.shoes.filter(s => !s.is_cutout).length;
    let badgeText = "空任务";
    let isReady = false;
    if (task.shoes.length > 0) {
      if (uncutCount > 0) {
        badgeText = `${uncutCount}张待抠`;
      } else {
        badgeText = "已就绪";
        isReady = true;
      }
    }

    if (isActive) {
      document.getElementById("header-task-name").textContent = task.name;
      document.getElementById("header-task-badge").textContent = isReady ? "已就绪" : (task.shoes.length ? `${uncutCount}待抠` : "未就绪");
    }

    card.innerHTML = `
      <div class="task-card-meta">
        <span class="task-card-title">${task.name}</span>
        <span class="task-card-sub">${task.sku ? `款号: ${task.sku}` : "未设款号"} · ${task.shoes.length} 色</span>
      </div>
      <div style="display: flex; align-items: center; gap: 6px;">
        <span class="task-card-badge ${isReady ? "ready" : ""}">${badgeText}</span>
        <button class="task-card-del-btn" title="删除该款式任务">✕</button>
      </div>
    `;

    card.querySelector(".task-card-del-btn").onclick = (e) => deleteTask(task.id, e);
    sidebarTasksList.appendChild(card);
  });
}

function renderPills(containerId, options, currentVal, onChange) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = "";
  options.forEach(opt => {
    const btn = document.createElement("button");
    btn.className = `pill-btn ${opt === currentVal ? "active" : ""}`;
    btn.textContent = opt;
    btn.onclick = () => {
      container.querySelectorAll(".pill-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      onChange(opt);
    };
    container.appendChild(btn);
  });
}

function renderTags(containerId, presets, onSelect) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = "";
  presets.forEach(p => {
    const span = document.createElement("span");
    span.className = "preset-chip";
    span.textContent = p;
    span.onclick = () => onSelect(p);
    container.appendChild(span);
  });
}

// --- Standard Logo Anatomical Slots & Smart Auto-Layout ---

const STANDARD_LOGO_SLOTS = {
  tongue: { rel_x: 0.38, rel_y: 0.08, scale: 1.0, name: "鞋舌口主标" },
  side:   { rel_x: 0.44, rel_y: 0.48, scale: 1.0, name: "鞋面侧腰标" },
  heel:   { rel_x: 0.12, rel_y: 0.35, scale: 0.65, name: "后跟大标" },
  strap:  { rel_x: 0.62, rel_y: 0.28, scale: 0.85, name: "织带副标" },
  toe:    { rel_x: 0.68, rel_y: 0.58, scale: 0.75, name: "鞋头/边条标" }
};
const SLOT_KEYS = ["tongue", "side", "heel", "strap", "toe"];

function autoLayoutShoeLogos(shoe) {
  if (!shoe || !shoe.logos || shoe.logos.length === 0) return;
  const usedSlots = new Set();
  shoe.logos.forEach((logo, idx) => {
    const def = state.logos_pool.find(l => l.id === logo.logo_id);
    let preferred = def ? def.default_type : null;
    if (!preferred || usedSlots.has(preferred)) {
      preferred = SLOT_KEYS.find(k => !usedSlots.has(k)) || "side";
    }
    usedSlots.add(preferred);
    const slotData = STANDARD_LOGO_SLOTS[preferred] || STANDARD_LOGO_SLOTS.side;
    
    logo.rel_x = slotData.rel_x;
    logo.rel_y = slotData.rel_y;
    logo.scale = (def && def.default_scale) ? def.default_scale : slotData.scale;
    logo.rotation = 0.0;
  });
}

function autoLayoutAllShoesLogos() {
  const task = getActiveTask();
  if (!task || task.shoes.length === 0) {
    showToast("当前款式尚未添加鞋款照片");
    return;
  }
  let totalCount = 0;
  task.shoes.forEach(shoe => {
    if (shoe.logos && shoe.logos.length > 0) {
      autoLayoutShoeLogos(shoe);
      totalCount += shoe.logos.length;
    }
  });
  updateStageUI();
  syncGroupsToServer();
  showToast(`🏷️ 标贴智能排版完成！已规整 ${totalCount} 枚标贴至鞋舌/侧腰/后跟标准区域`);
}

// --- Logo Pool Render inside Bottom Drawer (108款PDF官方标贴 + 常用核心标 + 自定义) ---

function getFilteredLogos() {
  let list = state.logos_pool || [];
  if (state.logo_category === "core") {
    list = list.filter(l => l.is_builtin && !l.is_pdf && !l.id?.startsWith("logo_22SS"));
  } else if (state.logo_category === "pdf") {
    list = list.filter(l => l.is_pdf || (l.id && l.id.startsWith("logo_22SS")));
  } else if (state.logo_category === "custom") {
    list = list.filter(l => !l.is_builtin && !l.is_pdf && !l.id?.startsWith("logo_22SS"));
  }
  if (state.logo_search_query) {
    const q = state.logo_search_query.trim().toLowerCase();
    list = list.filter(l => 
      (l.name && l.name.toLowerCase().includes(q)) || 
      (l.role && l.role.toLowerCase().includes(q)) ||
      (l.id && l.id.toLowerCase().includes(q))
    );
  }
  return list;
}

async function reloadLogosPool() {
  try {
    const res = await fetch("/api/logos");
    const data = await res.json();
    if (data.status === "success") {
      state.logos_pool = data.logos;
      renderLogoPool(state.logos_pool);
    }
  } catch (err) {
    console.warn("Failed to reload logos pool:", err);
  }
}

function renderLogoPool(passedLogos) {
  if (passedLogos && Array.isArray(passedLogos)) {
    state.logos_pool = passedLogos;
  }
  const grid = document.getElementById("logo-grid");
  if (!grid) return;
  grid.innerHTML = "";

  const allLogos = state.logos_pool || [];
  const countHint = document.getElementById("logos-count-hint");
  if (countHint) countHint.textContent = `${allLogos.length} 款`;

  const allTab = document.querySelector('.logo-tab-btn[data-cat="all"]');
  const pdfTab = document.querySelector('.logo-tab-btn[data-cat="pdf"]');
  const coreTab = document.querySelector('.logo-tab-btn[data-cat="core"]');
  const customTab = document.querySelector('.logo-tab-btn[data-cat="custom"]');

  const pdfCount = allLogos.filter(l => l.is_pdf || (l.id && l.id.startsWith("logo_22SS"))).length;
  const coreCount = allLogos.filter(l => l.is_builtin && !l.is_pdf && !l.id?.startsWith("logo_22SS")).length;
  const customCount = allLogos.filter(l => !l.is_builtin && !l.is_pdf && !l.id?.startsWith("logo_22SS")).length;

  if (allTab) allTab.textContent = `全部 (${allLogos.length})`;
  if (coreTab) coreTab.textContent = `常用核心标 (${coreCount})`;
  if (pdfTab) pdfTab.textContent = `22SS官方库 (${pdfCount})`;
  if (customTab) customTab.textContent = `自定义 (${customCount})`;

  const logos = getFilteredLogos();
  if (logos.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px;">🔍 没有找到匹配的标贴素材</div>`;
    return;
  }

  logos.forEach(logo => {
    const card = document.createElement("div");
    card.className = "logo-item-card";
    card.title = `点击添加到选中的鞋款（${logo.role}）`;

    const imgPath = logo.file.startsWith("/") ? logo.file : `/static/assets/${logo.file}`;
    card.innerHTML = `
      <div class="logo-thumb-wrapper">
        <img src="${imgPath}" alt="${logo.name}" class="logo-thumb-img">
      </div>
      <div class="logo-text-meta">
        <div class="logo-item-title" title="${logo.name}">${logo.name}</div>
        <div class="logo-item-role">${logo.role}</div>
      </div>
      <div class="logo-card-actions">
        <button class="logo-tool-btn btn-replace-logo" title="替换标贴图片">🔄</button>
        <button class="logo-tool-btn btn-edit-logo" title="修改名称与角色">✏️</button>
        ${!logo.is_builtin ? '<button class="logo-tool-btn danger btn-del-logo" title="删除此标贴">🗑️</button>' : ''}
      </div>
    `;

    // Tool Actions
    const btnReplace = card.querySelector(".btn-replace-logo");
    btnReplace.onclick = (e) => {
      e.stopPropagation();
      state.replacing_logo_id = logo.id;
      const inp = document.getElementById("logo-replace-file-input");
      if (inp) inp.click();
    };

    const btnEdit = card.querySelector(".btn-edit-logo");
    btnEdit.onclick = (e) => {
      e.stopPropagation();
      openEditLogoModal(logo);
    };

    const btnDel = card.querySelector(".btn-del-logo");
    if (btnDel) {
      btnDel.onclick = async (e) => {
        e.stopPropagation();
        if (!confirm(`确认删除标贴【${logo.name}】吗？`)) return;
        try {
          const res = await fetch(`/api/logos/${logo.id}`, { method: "DELETE" });
          const resData = await res.json();
          if (resData.status === "success") {
            showToast(`🗑️ 已删除标贴【${logo.name}】`);
            await reloadLogosPool();
          }
        } catch (err) {
          alert("删除标贴失败: " + err.message);
        }
      };
    }

    // Click Card Body: Add to selected shoe
    card.onclick = (e) => {
      if (e.target.closest(".logo-card-actions")) return;
      addLogoToSelectedShoe(logo);
    };

    grid.appendChild(card);
  });
}

function addLogoToSelectedShoe(logoDef) {
  const task = getActiveTask();
  if (!task || task.shoes.length === 0) {
    alert("请先上传或添加鞋子照片后再添加标贴！");
    return;
  }
  let targetShoe = task.shoes.find(s => s.id === state.selected_shoe_id) || task.shoes[0];
  state.selected_shoe_id = targetShoe.id;

  // 智能规避重叠：优先分配推荐槽位，若已被占则顺延空闲槽位
  const existingTypes = new Set();
  targetShoe.logos.forEach(l => {
    const lDef = state.logos_pool.find(item => item.id === l.logo_id);
    if (lDef && lDef.default_type) existingTypes.add(lDef.default_type);
  });

  let assignedType = logoDef.default_type || "side";
  if (existingTypes.has(assignedType)) {
    assignedType = SLOT_KEYS.find(k => !existingTypes.has(k)) || "side";
  }

  const slot = STANDARD_LOGO_SLOTS[assignedType] || STANDARD_LOGO_SLOTS.side;
  let relX = logoDef.default_rel_x ?? slot.rel_x;
  let relY = logoDef.default_rel_y ?? slot.rel_y;

  // 若同槽位已有标贴，稍微偏移避免叠死
  const sameSlotCount = targetShoe.logos.filter(l => Math.abs(l.rel_x - relX) < 0.05 && Math.abs(l.rel_y - relY) < 0.05).length;
  if (sameSlotCount > 0) {
    relX += sameSlotCount * 0.08;
    relY += sameSlotCount * 0.05;
  }

  targetShoe.logos.push({
    logo_id: logoDef.id,
    file: logoDef.file,
    rel_x: relX,
    rel_y: relY,
    scale: logoDef.default_scale ?? slot.scale ?? 1.0,
    rotation: 0.0
  });

  updateStageUI();
  syncGroupsToServer();
  showToast(`🏷️ 已智能定位放置【${logoDef.name}】至标准区域！`);
}

function openEditLogoModal(logo) {
  document.getElementById("edit-logo-id").value = logo.id;
  document.getElementById("input-edit-logo-name").value = logo.name;
  document.getElementById("input-edit-logo-role").value = logo.role;
  document.getElementById("select-edit-logo-type").value = logo.default_type || "side";
  document.getElementById("modal-edit-logo").classList.add("show");
}

// ==========================================================================
// Product Library (多颜色对应多图片 · 排版历史快照 · 一键套用)
// ==========================================================================

async function loadProductLibrary() {
  try {
    const res = await fetch("/api/products");
    const data = await res.json();
    if (data.status === "success") {
      state.products_db = data.products;
    }
  } catch (err) {
    console.warn("Failed to load products db:", err);
  }
}

function openProductLibraryModal() {
  renderProductGrid();
  modalProductLib.classList.add("show");
}

function closeProductLibraryModal() {
  modalProductLib.classList.remove("show");
  document.getElementById("prod-edit-form").style.display = "none";
}

function renderProductGrid(filterText = "") {
  const grid = document.getElementById("prod-library-grid");
  if (!grid) return;
  grid.innerHTML = "";

  const query = filterText.toLowerCase().trim();
  const list = state.products_db.filter(p => {
    if (!query) return true;
    return (p.sku && p.sku.toLowerCase().includes(query)) ||
           (p.name && p.name.toLowerCase().includes(query)) ||
           (p.fabrics && p.fabrics.toLowerCase().includes(query)) ||
           (p.soles && p.soles.toLowerCase().includes(query));
  });

  if (list.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 30px;">未检索到符合条件的款式档案，可点击上方【➕ 新建模版档案】录入！</div>`;
    return;
  }

  list.forEach(item => {
    const card = document.createElement("div");
    card.className = "prod-lib-card";
    
    // Multi-color gallery items (一色一图展示)
    let colorsHtml = "";
    if (item.colors && item.colors.length > 0) {
      colorsHtml = item.colors.map(col => {
        const img = col.image_url ? `<img src="${col.image_url}" class="prod-color-mini-img" alt="${col.color_name}">` : '';
        return `
          <span class="prod-color-thumb-chip">
            ${img}
            <span>${col.color_name}</span>
          </span>
        `;
      }).join("");
    } else if (item.default_colors && item.default_colors.length > 0) {
      colorsHtml = item.default_colors.map(c => `<span class="prod-color-thumb-chip"><span>${c}</span></span>`).join("");
    } else {
      colorsHtml = `<span style="font-size: 11px; color: var(--text-muted);">暂无录入颜色</span>`;
    }

    // Layout Snapshots List
    const snapshots = item.layout_history || [];
    let snapshotHtml = "";
    if (snapshots.length > 0) {
      const snapRows = snapshots.slice(0, 2).map((snap, sIdx) => `
        <div class="snapshot-item">
          <span>📸 ${snap.name} (${snap.shoes_count || snap.shoes?.length || 0}色)</span>
          <button class="btn-restore-snap" data-snap-idx="${sIdx}">⚡ 恢复标位</button>
        </div>
      `).join("");
      snapshotHtml = `
        <div class="prod-snapshots-box">
          <span style="font-size: 10px; font-weight: 700; color: var(--text-secondary);">排版记录 (${snapshots.length}个):</span>
          ${snapRows}
        </div>
      `;
    }

    const coverImgSrc = item.cover_image || (item.colors && item.colors[0]?.image_url) || "";
    const coverHtml = coverImgSrc 
      ? `<img src="${coverImgSrc}" alt="Cover" class="prod-cover-img">`
      : `<span class="prod-cover-empty">无照片</span>`;

    card.innerHTML = `
      <div class="prod-card-top">
        <div class="prod-cover-wrap">
          ${coverHtml}
        </div>
        <div class="prod-main-meta">
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span class="prod-sku-badge">${item.sku}</span>
            <div style="display: flex; gap: 4px;">
              <button class="qz-btn qz-btn-primary qz-btn-sm btn-apply-prod" title="一键将该款式的所有颜色图与规格载入当前画布！">⚡ 一键套用</button>
              <button class="qz-btn qz-btn-secondary qz-btn-sm btn-edit-prod" title="编辑款式与多色图">✏️</button>
              <button class="qz-btn qz-btn-secondary qz-btn-sm btn-del-prod" title="删除该款式" style="color: var(--danger);">🗑️</button>
            </div>
          </div>
          <span class="prod-name-text">${item.name || "未命名款式"}</span>
          <div class="prod-specs-box">
            <div><strong>面料：</strong>${item.fabrics || "-"}</div>
            <div><strong>鞋底：</strong>${item.soles || "-"}</div>
            <div><strong>参数：</strong>${item.category || "单鞋"} · ${item.season || "四季鞋"} · ${item.craft || "冷粘"} · 36码</div>
          </div>
        </div>
      </div>
      <div class="prod-colors-strip">${colorsHtml}</div>
      ${snapshotHtml}
    `;

    // Apply Product with All Its Colors & Images
    card.querySelector(".btn-apply-prod").onclick = () => {
      applyProductToCurrentTask(item);
    };

    // Restore Snapshot
    card.querySelectorAll(".btn-restore-snap").forEach(btn => {
      btn.onclick = () => {
        const snapIdx = parseInt(btn.dataset.snapIdx, 10);
        const targetSnap = snapshots[snapIdx];
        if (targetSnap) {
          restoreLayoutSnapshotToTask(targetSnap, item);
        }
      };
    });

    // Edit Product
    card.querySelector(".btn-edit-prod").onclick = () => {
      openProductEditForm(item);
    };

    // Delete Product
    card.querySelector(".btn-del-prod").onclick = () => {
      deleteProductFromDb(item.id, item.sku);
    };

    grid.appendChild(card);
  });
}

// 一键套用: 规格 + 全部颜色图片彻底带入当前任务！
function applyProductToCurrentTask(prod) {
  const task = getActiveTask();
  if (!task) return;

  task.sku = prod.sku;
  task.name = prod.name ? `${prod.name}` : `款式 ${prod.sku}`;
  task.fabrics = prod.fabrics;
  task.soles = prod.soles;
  task.category = prod.category || "单鞋";
  task.season = prod.season || "四季鞋";
  task.craft = prod.craft || "冷粘";
  task.size = prod.size || "36";

  // If product has multi-color images, import them directly into task.shoes!
  if (prod.colors && prod.colors.length > 0) {
    task.shoes = prod.colors.map((c, idx) => {
      const autoLogos = [
        { logo_id: "logo_square_boat", file: "logos/logo_square_boat.png", rel_x: 0.35, rel_y: 0.06, scale: 1.0, rotation: 0 },
        { logo_id: "logo_nvg_cursive", file: "logos/logo_nvg_cursive.png", rel_x: 0.28, rel_y: 0.44, scale: 1.0, rotation: 0 }
      ];
      return {
        id: `shoe_${Date.now()}_${idx}`,
        color_name: c.color_name,
        raw_filename: c.raw_filename || "",
        raw_url: c.image_url || (c.raw_filename ? `/static/uploads/${c.raw_filename}` : ""),
        cutout_filename: c.cutout_filename || (c.is_cutout ? c.raw_filename : null),
        cutout_url: c.image_url || (c.cutout_filename ? `/static/uploads/${c.cutout_filename}` : ""),
        is_cutout: !!c.is_cutout,
        width: 800,
        height: 500,
        offset_x: 0.0,
        offset_y: 0.0,
        scale_multiplier: 1.0,
        logos: autoLogos
      };
    });
    state.selected_shoe_id = task.shoes[0]?.id || null;
    triggerAiAutoLayout();
  }

  loadTaskIntoInputs(task);
  updateStageUI();
  renderTasksNav();
  renderShoeListCards();
  closeProductLibraryModal();
  syncGroupsToServer();
  showToast(`✅ 款式【${prod.sku}】(${prod.colors?.length || 0}色)已完整套用至当前任务！`);
}

function restoreLayoutSnapshotToTask(snapshot, prod) {
  const task = getActiveTask();
  if (!task) return;

  if (!snapshot.shoes || snapshot.shoes.length === 0) {
    alert("该排版快照未包含鞋子位置数据！");
    return;
  }

  task.sku = prod.sku;
  task.name = prod.name ? `${prod.name}` : `款式 ${prod.sku}`;
  task.fabrics = prod.fabrics;
  task.soles = prod.soles;
  task.season = prod.season;
  task.craft = prod.craft;
  task.category = prod.category;
  
  task.shoes = JSON.parse(JSON.stringify(snapshot.shoes));
  state.selected_shoe_id = task.shoes[0]?.id || null;

  loadTaskIntoInputs(task);
  updateStageUI();
  renderTasksNav();
  renderShoeListCards();
  closeProductLibraryModal();
  syncGroupsToServer();
  showToast(`⚡ 已成功恢复排版快照【${snapshot.name}】！`);
}

// Dynamic Product Form with Multi-Color Editor
function openProductEditForm(prod = null) {
  const formBox = document.getElementById("prod-edit-form");
  formBox.style.display = "block";
  
  if (prod) {
    document.getElementById("prod-form-title").textContent = `编辑款式档案：${prod.sku}`;
    formBox.dataset.editingId = prod.id;
    document.getElementById("form-prod-sku").value = prod.sku || "";
    document.getElementById("form-prod-name").value = prod.name || "";
    document.getElementById("form-prod-fabrics").value = prod.fabrics || "";
    document.getElementById("form-prod-soles").value = prod.soles || "";
    document.getElementById("form-prod-category").value = prod.category || "单鞋";
    document.getElementById("form-prod-craft").value = prod.craft || "冷粘";
    document.getElementById("form-prod-season").value = prod.season || "四季鞋";
    document.getElementById("form-prod-colors").value = (prod.default_colors || []).join(", ");
    
    state.form_colors_data = prod.colors ? JSON.parse(JSON.stringify(prod.colors)) : [];
  } else {
    document.getElementById("prod-form-title").textContent = "录入新款式资料档案 (支持多颜色图片)";
    delete formBox.dataset.editingId;
    document.getElementById("form-prod-sku").value = "";
    document.getElementById("form-prod-name").value = "";
    document.getElementById("form-prod-fabrics").value = "牛反绒";
    document.getElementById("form-prod-soles").value = "橡胶大底";
    document.getElementById("form-prod-category").value = "单鞋";
    document.getElementById("form-prod-craft").value = "冷粘";
    document.getElementById("form-prod-season").value = "四季鞋";
    document.getElementById("form-prod-colors").value = "黑色, 酒红, 粉色, 米白";
    
    state.form_colors_data = [
      { id: "col_1", color_name: "黑色", image_url: "", raw_filename: "", is_cutout: false },
      { id: "col_2", color_name: "粉色", image_url: "", raw_filename: "", is_cutout: false }
    ];
  }
  renderFormColorRows();
}

function renderFormColorRows() {
  const list = document.getElementById("form-colors-editor-list");
  if (!list) return;
  list.innerHTML = "";

  state.form_colors_data.forEach((col, idx) => {
    const row = document.createElement("div");
    row.className = "color-edit-row";

    const thumbSrc = col.image_url || (col.raw_filename ? `/static/uploads/${col.raw_filename}` : "");
    const imgHtml = thumbSrc ? `<img src="${thumbSrc}" class="color-edit-thumb">` : `<div class="color-edit-thumb" style="display:flex;align-items:center;justify-content:center;font-size:9px;color:var(--text-muted);">无图</div>`;

    row.innerHTML = `
      <input type="text" class="color-edit-input" value="${col.color_name}" placeholder="颜色名">
      ${imgHtml}
      <button type="button" class="color-edit-upload-btn btn-row-upload">📷 传图</button>
      <input type="file" accept="image/*" class="row-file-input" style="display:none;">
      <button type="button" class="color-edit-del-btn btn-row-del" title="删除该颜色">✕</button>
    `;

    const inputName = row.querySelector(".color-edit-input");
    inputName.oninput = (e) => {
      col.color_name = e.target.value;
    };

    const fileInput = row.querySelector(".row-file-input");
    row.querySelector(".btn-row-upload").onclick = () => fileInput.click();
    fileInput.onchange = async (e) => {
      if (e.target.files && e.target.files[0]) {
        const file = e.target.files[0];
        const formData = new FormData();
        formData.append("file", file);
        showLoading(`正在上传【${col.color_name || '颜色图'}】...`);
        try {
          const res = await fetch("/api/upload-raw", { method: "POST", body: formData });
          const data = await res.json();
          if (data.status === "success") {
            col.raw_filename = data.raw_filename;
            col.image_url = data.raw_url;
            col.is_cutout = false;
            renderFormColorRows();
            showToast(`✅ 【${col.color_name}】鞋图上传成功！`);
          }
        } catch (err) {
          alert("上传失败: " + err.message);
        } finally {
          hideLoading();
        }
      }
    };

    row.querySelector(".btn-row-del").onclick = () => {
      state.form_colors_data.splice(idx, 1);
      renderFormColorRows();
    };

    list.appendChild(row);
  });
}

function handleAddFormColorRow() {
  const nextIdx = state.form_colors_data.length + 1;
  const colorName = DEFAULT_COLOR_PALETTE[state.form_colors_data.length % DEFAULT_COLOR_PALETTE.length] || `颜色${nextIdx}`;
  state.form_colors_data.push({
    id: `col_${Date.now()}_${nextIdx}`,
    color_name: colorName,
    image_url: "",
    raw_filename: "",
    is_cutout: false
  });
  renderFormColorRows();
}

async function saveProductItemFromForm() {
  const formBox = document.getElementById("prod-edit-form");
  const sku = document.getElementById("form-prod-sku").value.trim();
  if (!sku) {
    alert("款号必须填写！");
    return;
  }
  const name = document.getElementById("form-prod-name").value.trim();
  const fabrics = document.getElementById("form-prod-fabrics").value.trim();
  const soles = document.getElementById("form-prod-soles").value.trim();
  const category = document.getElementById("form-prod-category").value.trim() || "单鞋";
  const craft = document.getElementById("form-prod-craft").value.trim() || "冷粘";
  const season = document.getElementById("form-prod-season").value.trim() || "四季鞋";
  const colorsRaw = document.getElementById("form-prod-colors").value.trim();
  
  const editingId = formBox.dataset.editingId;
  const existingProd = state.products_db.find(p => p.id === editingId || p.sku === sku);

  // Collect color list from dynamic editor
  const finalColors = state.form_colors_data.map(c => ({
    id: c.id || `col_${Date.now()}`,
    color_name: c.color_name.trim(),
    image_url: c.image_url || "",
    raw_filename: c.raw_filename || "",
    cutout_filename: c.cutout_filename || (c.is_cutout ? c.raw_filename : null),
    is_cutout: !!c.is_cutout
  })).filter(c => c.color_name);

  const default_colors = finalColors.map(c => c.color_name);
  if (default_colors.length === 0 && colorsRaw) {
    colorsRaw.split(/[,，\s]+/).filter(Boolean).forEach(c => default_colors.push(c));
  }

  let coverImg = existingProd?.cover_image || null;
  if (!coverImg && finalColors.length > 0) {
    coverImg = finalColors[0].image_url || (finalColors[0].raw_filename ? `/static/uploads/${finalColors[0].raw_filename}` : null);
  }

  const payload = {
    id: editingId || undefined,
    sku,
    name: name || `款式 ${sku}`,
    fabrics,
    soles,
    category,
    craft,
    season,
    size: "36",
    default_colors,
    colors: finalColors,
    cover_image: coverImg,
    layout_history: existingProd?.layout_history || []
  };

  showLoading("正在保存款式资料档案...");
  try {
    const url = editingId ? `/api/products/${editingId}` : "/api/products";
    const method = editingId ? "PUT" : "POST";
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === "success") {
      await loadProductLibrary();
      formBox.style.display = "none";
      renderProductGrid();
      showToast(`💾 款式【${sku}】已成功存入资料库！`);
    }
  } catch (err) {
    alert("保存失败: " + err.message);
  } finally {
    hideLoading();
  }
}

async function deleteProductFromDb(prodId, sku) {
  if (!confirm(`确定从款式资料库中删除【${sku}】吗？`)) return;
  showLoading("正在删除款式档案...");
  try {
    const res = await fetch(`/api/products/${prodId}`, { method: "DELETE" });
    const data = await res.json();
    if (data.status === "success") {
      state.products_db = state.products_db.filter(p => p.id !== prodId);
      renderProductGrid();
      showToast(`🗑️ 款式【${sku}】已从资料库移除。`);
    }
  } catch (err) {
    alert("删除失败: " + err.message);
  } finally {
    hideLoading();
  }
}

// 主界面快捷存模版: 将当前任务的规格、所有的颜色图以及排版位置一并存入款式资料库
async function handleQuickSaveCurrentToProdLib() {
  const task = getActiveTask();
  if (!task || !task.sku) {
    alert("请先填写当前款式的货号/款号！");
    return;
  }

  const default_colors = task.shoes.map(s => s.color_name).filter(Boolean);
  const colors = task.shoes.map(s => ({
    id: s.id,
    color_name: s.color_name,
    image_url: s.cutout_url || s.raw_url,
    raw_filename: s.raw_filename,
    cutout_filename: s.cutout_filename,
    is_cutout: s.is_cutout
  }));

  let coverImg = null;
  for (const s of task.shoes) {
    if (s.cutout_url) { coverImg = s.cutout_url; break; }
    else if (s.raw_url) { coverImg = s.raw_url; break; }
  }

  const existing = state.products_db.find(p => p.sku === task.sku);

  const payload = {
    sku: task.sku,
    name: task.name,
    fabrics: task.fabrics,
    soles: task.soles,
    category: task.category,
    craft: task.craft,
    season: task.season,
    size: task.size,
    default_colors,
    colors,
    cover_image: coverImg || existing?.cover_image || null,
    layout_history: existing?.layout_history || []
  };

  showLoading(`正在将【${task.sku}】规格与图片存入产品库...`);
  try {
    const res = await fetch("/api/products", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === "success") {
      if (task.shoes.length > 0) {
        await saveCurrentLayoutSnapshotSilently(task.sku, `${task.shoes.length}色标准排版`);
      }
      await loadProductLibrary();
      showToast(`💾 款式【${task.sku}】已成功同步至产品库模版！`);
    }
  } catch (err) {
    alert("保存失败: " + err.message);
  } finally {
    hideLoading();
  }
}

async function saveCurrentLayoutSnapshotSilently(sku, snapName) {
  const task = getActiveTask();
  if (!task || task.shoes.length === 0) return;
  try {
    await fetch(`/api/products/${sku}/snapshot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: snapName,
        shoes: task.shoes.map(s => ({
          id: s.id,
          color_name: s.color_name,
          raw_filename: s.raw_filename,
          cutout_filename: s.cutout_filename,
          is_cutout: s.is_cutout,
          offset_x: s.offset_x ?? 0.0,
          offset_y: s.offset_y ?? 0.0,
          scale_multiplier: s.scale_multiplier ?? 1.0,
          logos: s.logos
        }))
      })
    });
  } catch (e) {
    console.warn("Silent snapshot failed", e);
  }
}

async function handleSaveLayoutSnapshot() {
  const task = getActiveTask();
  if (!task || !task.sku) {
    alert("请先填写款号，才能保存排版记录！");
    return;
  }
  if (task.shoes.length === 0) {
    alert("当前画布没有任何鞋款，无法保存排版！");
    return;
  }

  const snapName = prompt("请输入排版记录名称：\n例如：4色四宫格标位 / 6色矩阵排版", `${task.shoes.length}色 送审排版记录`);
  if (!snapName || !snapName.trim()) return;

  showLoading("正在保存排版快照至资料库...");
  try {
    const res = await fetch(`/api/products/${task.sku}/snapshot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: snapName.trim(),
        shoes: task.shoes.map(s => ({
          id: s.id,
          color_name: s.color_name,
          raw_filename: s.raw_filename,
          cutout_filename: s.cutout_filename,
          is_cutout: s.is_cutout,
          offset_x: s.offset_x ?? 0.0,
          offset_y: s.offset_y ?? 0.0,
          scale_multiplier: s.scale_multiplier ?? 1.0,
          logos: s.logos
        }))
      })
    });
    const data = await res.json();
    if (data.status === "success") {
      await loadProductLibrary();
      showToast(`📸 排版快照【${snapName.trim()}】已存入资料库！`);
    }
  } catch (err) {
    alert("保存快照失败: " + err.message);
  } finally {
    hideLoading();
  }
}

// --- AI Natural Language Parsing Modal ---
function openAiParserModal() {
  modalAiParser.classList.add("show");
  document.getElementById("ai-parse-input").focus();
}

function closeAiParserModal() {
  modalAiParser.classList.remove("show");
}

async function handleAiParseSubmit() {
  const text = document.getElementById("ai-parse-input").value.trim();
  if (!text) {
    alert("请输入聊天记录或版单文本！");
    return;
  }

  showLoading("✨ AI 正在极速分析文本抽取版单参数...");
  try {
    const res = await fetch("/api/ai/parse-spec", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: text })
    });
    const data = await res.json();
    if (data.status === "success") {
      const p = data.parsed;
      const task = getActiveTask();
      if (task) {
        if (p.sku) {
          task.sku = p.sku;
          task.name = `款式 ${p.sku}`;
        }
        if (p.category) task.category = p.category;
        if (p.season) task.season = p.season;
        if (p.craft) task.craft = p.craft;
        if (p.fabrics) task.fabrics = p.fabrics;
        if (p.soles) task.soles = p.soles;

        // If colors were detected and task has shoes, assign colors
        if (p.colors && p.colors.length > 0) {
          p.colors.forEach((col, idx) => {
            if (task.shoes[idx]) {
              task.shoes[idx].color_name = col;
            }
          });
        }

        loadTaskIntoInputs(task);
        updateStageUI();
        renderTasksNav();
        renderShoeListCards();
        closeAiParserModal();
        syncGroupsToServer();
        showToast("⚡ AI 参数识别成功，已完整写入当前款式！");
      }
    }
  } catch (err) {
    alert("AI 解析失败: " + err.message);
  } finally {
    hideLoading();
  }
}

// --- Event Listeners Setup ---
function setupEventListeners() {
  // Groups
  groupSelectEl.onchange = (e) => switchGroup(e.target.value);
  document.getElementById("btn-create-group").onclick = handleCreateGroup;
  document.getElementById("btn-rename-group").onclick = handleOpenRenameGroupModal;
  document.getElementById("btn-delete-group").onclick = handleOpenDeleteGroupModal;

  // Modals close buttons
  document.getElementById("btn-close-rename-modal").onclick = () => modalRenameGroup.classList.remove("show");
  document.getElementById("btn-cancel-rename-group").onclick = () => modalRenameGroup.classList.remove("show");
  document.getElementById("btn-confirm-rename-group").onclick = handleConfirmRenameGroup;

  document.getElementById("btn-close-delete-modal").onclick = () => modalDeleteGroup.classList.remove("show");
  document.getElementById("btn-cancel-delete-group").onclick = () => modalDeleteGroup.classList.remove("show");
  document.getElementById("btn-confirm-delete-group").onclick = handleConfirmDeleteGroup;

  // Tasks
  document.getElementById("btn-create-task").onclick = createNewTask;

  // Product Library
  document.getElementById("btn-open-prod-lib").onclick = openProductLibraryModal;
  document.getElementById("btn-quick-import-prod").onclick = openProductLibraryModal;
  document.getElementById("btn-close-prod-modal").onclick = closeProductLibraryModal;
  document.getElementById("btn-close-prod-modal-foot").onclick = closeProductLibraryModal;
  document.getElementById("btn-save-to-prod-lib").onclick = handleQuickSaveCurrentToProdLib;
  document.getElementById("btn-save-layout-snapshot").onclick = handleSaveLayoutSnapshot;

  document.getElementById("btn-new-prod-item").onclick = () => openProductEditForm(null);
  document.getElementById("btn-cancel-prod-edit").onclick = () => {
    document.getElementById("prod-edit-form").style.display = "none";
  };
  document.getElementById("btn-save-prod-item").onclick = saveProductItemFromForm;
  document.getElementById("btn-add-form-color-row").onclick = handleAddFormColorRow;

  document.getElementById("prod-search-input").oninput = (e) => {
    renderProductGrid(e.target.value);
  };

  // AI Modal
  document.getElementById("btn-ai-parse-modal").onclick = openAiParserModal;
  document.getElementById("btn-close-ai-modal").onclick = closeAiParserModal;
  document.getElementById("btn-cancel-ai-parse").onclick = closeAiParserModal;
  document.getElementById("btn-submit-ai-parse").onclick = handleAiParseSubmit;

  // LAN Share pill copy
  document.getElementById("lan-share-badge").onclick = () => {
    const text = document.getElementById("lan-url-text").textContent;
    navigator.clipboard.writeText(text).then(() => {
      showToast(`📋 局域网访问地址已复制：${text}`);
    }).catch(() => {
      prompt("请复制局域网访问地址：", text);
    });
  };

  // Inputs Realtime Sync
  const task = () => getActiveTask();
  document.getElementById("input-sku").addEventListener("input", (e) => {
    const t = task();
    if (!t) return;
    t.sku = e.target.value;
    t.name = e.target.value ? `款式 ${e.target.value}` : "未命名款式";
    document.getElementById("header-task-name").textContent = t.name;
    renderTasksNav();
    syncGroupsToServer();
  });
  document.getElementById("input-material-code").addEventListener("input", (e) => {
    const t = task(); if (t) { t.material_code = e.target.value; updateStageUI(); syncGroupsToServer(); }
  });
  document.getElementById("input-size").addEventListener("input", (e) => {
    const t = task(); if (t) { t.size = e.target.value; updateStageUI(); syncGroupsToServer(); }
  });
  document.getElementById("input-fabrics").addEventListener("input", (e) => {
    const t = task(); if (t) { t.fabrics = e.target.value; updateStageUI(); syncGroupsToServer(); }
  });
  document.getElementById("input-soles").addEventListener("input", (e) => {
    const t = task(); if (t) { t.soles = e.target.value; updateStageUI(); syncGroupsToServer(); }
  });

  // Action Buttons
  document.getElementById("btn-ai-layout").onclick = triggerAiAutoLayout;
  const btnAutoLogos = document.getElementById("btn-auto-layout-logos");
  if (btnAutoLogos) btnAutoLogos.onclick = autoLayoutAllShoesLogos;
  
  const btnQuickLogos = document.getElementById("btn-quick-auto-align-logos");
  if (btnQuickLogos) {
    btnQuickLogos.onclick = () => {
      const t = getActiveTask();
      const s = t?.shoes.find(x => x.id === state.selected_shoe_id) || t?.shoes[0];
      if (s) {
        autoLayoutShoeLogos(s);
        updateStageUI();
        syncGroupsToServer();
        showToast(`🏷️ 已智能规整【${s.color_name || '当前鞋款'}】标贴！`);
      } else {
        showToast("当前款式尚未添加鞋款照片");
      }
    };
  }

  // Logo Modals
  const btnOpenAddLogo = document.getElementById("btn-open-add-logo-modal");
  if (btnOpenAddLogo) btnOpenAddLogo.onclick = () => document.getElementById("modal-add-logo").classList.add("show");
  
  const btnCloseAddLogo = document.getElementById("btn-close-add-logo-modal");
  if (btnCloseAddLogo) btnCloseAddLogo.onclick = () => document.getElementById("modal-add-logo").classList.remove("show");
  
  const btnCancelAddLogo = document.getElementById("btn-cancel-add-logo");
  if (btnCancelAddLogo) btnCancelAddLogo.onclick = () => document.getElementById("modal-add-logo").classList.remove("show");
  
  const btnConfirmAddLogo = document.getElementById("btn-confirm-add-logo");
  if (btnConfirmAddLogo) btnConfirmAddLogo.onclick = handleConfirmAddLogo;

  const btnCloseEditLogo = document.getElementById("btn-close-edit-logo-modal");
  if (btnCloseEditLogo) btnCloseEditLogo.onclick = () => document.getElementById("modal-edit-logo").classList.remove("show");
  
  const btnCancelEditLogo = document.getElementById("btn-cancel-edit-logo");
  if (btnCancelEditLogo) btnCancelEditLogo.onclick = () => document.getElementById("modal-edit-logo").classList.remove("show");
  
  const btnConfirmEditLogo = document.getElementById("btn-confirm-edit-logo");
  if (btnConfirmEditLogo) btnConfirmEditLogo.onclick = handleConfirmEditLogo;

  initTemplateHeaderEditor();
  initInPlaceReplacers();

  document.getElementById("btn-batch-cutout").onclick = triggerBatchCutout;
  document.getElementById("btn-render-current").onclick = () => renderAndExportCurrent(false);
  document.getElementById("btn-batch-render-all").onclick = batchRenderActiveGroup;
  document.getElementById("btn-open-folder").onclick = openOutputFolder;

  // Drawer Toggle (Collapse / Expand)
  const drawer = document.getElementById("bottom-drawer");
  const toggleBtn = document.getElementById("btn-toggle-drawer");
  const icon = document.getElementById("drawer-collapse-icon");
  toggleBtn.onclick = () => {
    drawer.classList.toggle("collapsed");
    icon.textContent = drawer.classList.contains("collapsed") ? "▲" : "▼";
    setTimeout(setupStageScale, 220);
  };

  // Upload Dropzone
  const dropzone = document.getElementById("upload-dropzone");
  const fileInput = document.getElementById("file-input");

  dropzone.onclick = () => fileInput.click();
  dropzone.ondragover = (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "var(--brand-primary)";
    dropzone.style.background = "var(--brand-primary-light)";
  };
  dropzone.ondragleave = () => {
    dropzone.style.borderColor = "var(--border-light)";
    dropzone.style.background = "var(--bg-input)";
  };
  dropzone.ondrop = async (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "var(--border-light)";
    dropzone.style.background = "var(--bg-input)";
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFastRawUpload(e.dataTransfer.files);
    }
  };

  fileInput.onchange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFastRawUpload(e.target.files);
    }
  };
}

// --- Logo Template Add / Edit Handlers ---

async function handleConfirmAddLogo() {
  const name = document.getElementById("input-new-logo-name").value.trim();
  const role = document.getElementById("input-new-logo-role").value.trim();
  const type = document.getElementById("select-new-logo-type").value;
  const fileInput = document.getElementById("input-new-logo-file");
  const file = fileInput.files[0];

  if (!name) {
    alert("请输入标贴名称！");
    return;
  }
  if (!file) {
    alert("请选择标贴图片！");
    return;
  }

  showLoading("正在上传并保存新标贴模版...");
  try {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", name);
    fd.append("role", role);
    fd.append("default_type", type);

    const res = await fetch("/api/logos/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (data.status === "success") {
      document.getElementById("modal-add-logo").classList.remove("show");
      document.getElementById("input-new-logo-name").value = "";
      document.getElementById("input-new-logo-role").value = "";
      fileInput.value = "";
      await reloadLogosPool();
      showToast(`🏷️ 新增标贴【${name}】成功！已加入标贴箱`);
    } else {
      throw new Error(data.detail || "上传失败");
    }
  } catch (err) {
    alert("新增标贴失败: " + err.message);
  } finally {
    hideLoading();
  }
}

async function handleConfirmEditLogo() {
  const id = document.getElementById("edit-logo-id").value;
  const name = document.getElementById("input-edit-logo-name").value.trim();
  const role = document.getElementById("input-edit-logo-role").value.trim();
  const type = document.getElementById("select-edit-logo-type").value;

  if (!name) {
    alert("请输入标贴名称！");
    return;
  }

  try {
    const res = await fetch(`/api/logos/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, role, default_type: type })
    });
    const data = await res.json();
    if (data.status === "success") {
      document.getElementById("modal-edit-logo").classList.remove("show");
      await reloadLogosPool();
      showToast("✏️ 标贴信息已修改！");
    } else {
      throw new Error(data.detail || "修改失败");
    }
  } catch (err) {
    alert("修改标贴失败: " + err.message);
  }
}

// --- In-place Replacers for Shoe Photos and Logo Templates ---

function initInPlaceReplacers() {
  // Shoe Photo In-place Replacer
  const shoeInput = document.getElementById("shoe-replace-file-input");
  if (shoeInput) {
    shoeInput.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file || !state.replacing_shoe_id) return;
      const task = getActiveTask();
      if (!task) return;
      const shoe = task.shoes.find(s => s.id === state.replacing_shoe_id);
      if (!shoe) return;

      showLoading(`正在替换【${shoe.color_name || '当前鞋款'}】照片并执行调优去底...`);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const upRes = await fetch("/api/upload", { method: "POST", body: fd });
        const upData = await upRes.json();
        if (upData.status !== "success") throw new Error(upData.detail || "上传失败");

        // Execute fine-tuned cutout
        const cutRes = await fetch("/api/cutout-batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filenames: [upData.raw_filename] })
        });
        const cutData = await cutRes.json();
        const cResult = cutData.results ? cutData.results[0] : null;

        shoe.raw_filename = upData.raw_filename;
        shoe.raw_url = upData.raw_url;
        if (cResult && cResult.status === "success") {
          shoe.cutout_filename = cResult.cutout_filename;
          shoe.cutout_url = cResult.cutout_url;
          shoe.width = cResult.width;
          shoe.height = cResult.height;
          shoe.is_cutout = true;
        } else {
          shoe.width = upData.width;
          shoe.height = upData.height;
          shoe.is_cutout = false;
        }

        updateStageUI();
        renderShoeListCards();
        syncGroupsToServer();
        showToast(`🔄 已成功为【${shoe.color_name || '当前鞋款'}】替换照片并自动去底！`);
      } catch (err) {
        alert("换图失败: " + err.message);
      } finally {
        hideLoading();
        shoeInput.value = "";
      }
    };
  }

  // Logo Image In-place Replacer
  const logoInput = document.getElementById("logo-replace-file-input");
  if (logoInput) {
    logoInput.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file || !state.replacing_logo_id) return;
      showLoading("正在更新标贴图片...");
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch(`/api/logos/${state.replacing_logo_id}/replace`, {
          method: "POST",
          body: fd
        });
        const data = await res.json();
        if (data.status === "success") {
          await reloadLogosPool();
          updateStageUI();
          showToast("🔄 标贴图片已更新！");
        } else {
          throw new Error(data.detail || "替换失败");
        }
      } catch (err) {
        alert("替换标贴图片失败: " + err.message);
      } finally {
        hideLoading();
        logoInput.value = "";
      }
    };
  }
}

// --- Dynamic Vector Table Lines Layer ---
function renderTableVectorLines() {
  const svg = document.getElementById("table-lines-svg");
  if (!svg) return;
  const cfg = state.template_config || {};
  const lines = cfg.lines || {
    border_width: 4,
    border_color: "#000000",
    inner_width: 2,
    inner_color: "#000000",
    divider_x: 840,
    left_table_label_w: 285
  };

  const bw = lines.border_width || 4;
  const bc = lines.border_color || "#000000";
  const iw = lines.inner_width || 2;
  const ic = lines.inner_color || "#000000";
  const divX = lines.divider_x || 840;
  const lblW = lines.left_table_label_w || 285;

  const hRows = [374, 491, 608, 724, 840, 955, 1070, 1185, 1300, 1422];

  let svgHtml = `
    <!-- Outer Border -->
    <rect x="28" y="107" width="3394" height="2298" fill="none" stroke="${bc}" stroke-width="${bw}"/>
    <!-- Header Horizontal Line -->
    <line x1="28" y1="258" x2="3422" y2="258" stroke="${bc}" stroke-width="${bw}"/>
    <!-- Reviewer Vertical Lines -->
    <line x1="2650" y1="107" x2="2650" y2="258" stroke="${ic}" stroke-width="${iw}"/>
    <line x1="3040" y1="107" x2="3040" y2="258" stroke="${ic}" stroke-width="${iw}"/>
    <!-- Main Left-Right Divider -->
    <line x1="${divX}" y1="258" x2="${divX}" y2="2405" stroke="${bc}" stroke-width="${bw}"/>
    <!-- Left Labels Divider -->
    <line x1="${lblW}" y1="258" x2="${lblW}" y2="1422" stroke="${ic}" stroke-width="${iw}"/>
  `;

  // Horizontal Grid Lines on the left
  hRows.forEach(y => {
    svgHtml += `<line x1="28" y1="${y}" x2="${divX}" y2="${y}" stroke="${ic}" stroke-width="${iw}"/>`;
  });

  // Size sub-cell line in row 4 (724 to 840)
  svgHtml += `<line x1="470" y1="724" x2="470" y2="840" stroke="${ic}" stroke-width="${iw}"/>`;

  svg.innerHTML = svgHtml;
}

// --- Dynamic Interactive Editable Table Texts System ---
function renderTableTexts() {
  const cfg = state.template_config || {};
  const fonts = cfg.fonts || {};
  const lines = cfg.lines || { divider_x: 840, left_table_label_w: 285 };
  const task = getActiveTask();
  if (!task) return;

  // 1. Header Brand Logo
  const logoImg = document.getElementById("stage-header-logo-img");
  if (logoImg && cfg.logo_url) {
    logoImg.src = cfg.logo_url;
  }

  // 2. Header Title
  const titleEl = document.getElementById("text-tmpl-title");
  if (titleEl) {
    const valSpan = titleEl.querySelector(".text-val");
    if (valSpan) valSpan.textContent = cfg.title || "臻兴科技开发样品单";
    titleEl.style.fontFamily = fonts.title_font || "Microsoft YaHei";
    titleEl.style.fontSize = `${fonts.title_size || 76}px`;
    titleEl.style.fontWeight = fonts.title_weight || "bold";
    titleEl.style.color = fonts.title_color || "#000000";
    titleEl.onclick = (e) => {
      e.stopPropagation();
      openTypoBar("title", "表头标题");
    };
  }

  // 3. Reviewer & Re-reviewer
  const revEl = document.getElementById("text-tmpl-reviewers");
  if (revEl) {
    const rev1 = revEl.querySelector(".text-val-rev1");
    const rev2 = revEl.querySelector(".text-val-rev2");
    if (rev1) rev1.textContent = cfg.reviewer || "审核:";
    if (rev2) rev2.textContent = cfg.re_reviewer || "复核:";
    revEl.style.fontFamily = fonts.table_font || "Microsoft YaHei";
    revEl.style.color = fonts.table_color || "#000000";
    revEl.onclick = (e) => {
      e.stopPropagation();
      openTypoBar("reviewer", "审核/复核文本");
    };
  }

  // 4. Category Title (Large Text: 成人女鞋)
  const catTitleEl = document.getElementById("text-tmpl-category-title");
  if (catTitleEl) {
    const valSpan = catTitleEl.querySelector(".text-val");
    if (valSpan) valSpan.textContent = cfg.category_title || "成人女鞋";
    catTitleEl.style.fontFamily = fonts.category_font || "Microsoft YaHei";
    catTitleEl.style.fontSize = `${fonts.category_size || 72}px`;
    catTitleEl.style.fontWeight = fonts.category_weight || "bold";
    catTitleEl.style.color = fonts.category_color || "#000000";
    catTitleEl.onclick = (e) => {
      e.stopPropagation();
      openTypoBar("category_title", "品类大标题");
    };
  }

  // 5. Fabrics & Soles Box
  const fabricsEl = document.getElementById("text-tmpl-fabrics");
  if (fabricsEl) {
    const lblFabrics = cfg.labels?.fabrics || "面料:";
    fabricsEl.innerHTML = `${lblFabrics} <span class="val-part">${task.fabrics || "牛反绒+沙丁布"}</span>`;
    fabricsEl.style.fontFamily = fonts.table_font || "Microsoft YaHei";
    fabricsEl.style.color = fonts.table_color || "#000000";
    fabricsEl.onclick = (e) => {
      e.stopPropagation();
      openTypoBar("fabrics", "面料组合");
    };
  }

  const solesEl = document.getElementById("text-tmpl-soles");
  if (solesEl) {
    const lblSoles = cfg.labels?.soles || "鞋底:";
    solesEl.innerHTML = `${lblSoles} <span class="val-part">${task.soles || "橡胶大底"}</span>`;
    solesEl.style.fontFamily = fonts.table_font || "Microsoft YaHei";
    solesEl.style.color = fonts.table_color || "#000000";
    solesEl.onclick = (e) => {
      e.stopPropagation();
      openTypoBar("soles", "鞋底材质");
    };
  }

  // 6. Left Specifications Grid (10 Rows)
  const leftGrid = document.getElementById("left-table-grid");
  if (leftGrid) {
    const divX = lines.divider_x || 840;
    const lblW = lines.left_table_label_w || 285;
    const gridW = divX - 28;
    leftGrid.style.width = `${gridW}px`;

    const rowsDef = [
      { key: "sku", labelKey: "sku", labelDef: "货号:", val: task.sku || "", top: 0, h: 116 },
      { key: "season", labelKey: "season", labelDef: "季节:", val: task.season || "", top: 116, h: 117 },
      { key: "craft", labelKey: "craft", labelDef: "工艺:", val: task.craft || "", top: 233, h: 117 },
      { key: "category", labelKey: "category", labelDef: "类别:", val: task.category || "", top: 350, h: 116 },
      { key: "size", labelKey: "last", labelDef: "楦型:", sublabelKey: "size", sublabelDef: "尺码", val: task.size || "", top: 466, h: 116, isSize: true },
      { key: "designer", labelKey: "designer", labelDef: "设计:", val: task.designer || "", top: 582, h: 115 },
      { key: "patternmaker", labelKey: "patternmaker", labelDef: "版师:", val: task.patternmaker || "", top: 697, h: 115 },
      { key: "order", labelKey: "order", labelDef: "打单:", val: task.order || "", top: 812, h: 115 },
      { key: "print", labelKey: "print", labelDef: "印花:", val: task.print || "", top: 927, h: 115 },
      { key: "material_code", labelKey: "material_code", labelDef: "素材编号:", val: task.material_code || "", top: 1042, h: 122 }
    ];

    leftGrid.innerHTML = "";
    rowsDef.forEach(r => {
      const rowEl = document.createElement("div");
      rowEl.className = "left-grid-row";
      rowEl.style.top = `${r.top}px`;
      rowEl.style.height = `${r.h}px`;

      const labelText = cfg.labels?.[r.labelKey] || r.labelDef;

      if (r.isSize) {
        const sublabelText = cfg.labels?.[r.sublabelKey] || r.sublabelDef;
        rowEl.innerHTML = `
          <div class="left-row-lbl" data-field="label_${r.labelKey}" title="点击修改标签文字">${labelText}</div>
          <div class="left-row-sublbl" data-field="label_${r.sublabelKey}" title="点击修改标签文字">${sublabelText}</div>
          <div class="left-row-val" data-field="${r.key}" title="点击修改内容或字体">${r.val}</div>
        `;
      } else {
        rowEl.innerHTML = `
          <div class="left-row-lbl" data-field="label_${r.labelKey}" title="点击修改标签文字">${labelText}</div>
          <div class="left-row-val" data-field="${r.key}" title="点击修改内容或字体">${r.val}</div>
        `;
      }

      // Apply font styles to row labels and values
      const lblNode = rowEl.querySelector(".left-row-lbl");
      if (lblNode) {
        lblNode.style.fontFamily = fonts.labels_font || "Microsoft YaHei";
        lblNode.style.fontSize = `${fonts.labels_size || 48}px`;
        lblNode.style.fontWeight = fonts.labels_weight || "normal";
        lblNode.style.color = fonts.labels_color || "#000000";
        lblNode.style.width = `${lblW - 28}px`;
        lblNode.onclick = (e) => {
          e.stopPropagation();
          openTypoBar(`label_${r.labelKey}`, `标签【${labelText}】`);
        };
      }

      const sublblNode = rowEl.querySelector(".left-row-sublbl");
      if (sublblNode) {
        sublblNode.style.fontFamily = fonts.labels_font || "Microsoft YaHei";
        sublblNode.style.fontSize = `${fonts.labels_size || 48}px`;
        sublblNode.style.fontWeight = fonts.labels_weight || "normal";
        sublblNode.style.color = fonts.labels_color || "#000000";
        sublblNode.onclick = (e) => {
          e.stopPropagation();
          openTypoBar(`label_${r.sublabelKey}`, `标签【${sublblNode.textContent}】`);
        };
      }

      const valNode = rowEl.querySelector(".left-row-val");
      if (valNode) {
        valNode.style.fontFamily = fonts.table_font || "Microsoft YaHei";
        valNode.style.fontSize = `${fonts.table_size || 52}px`;
        valNode.style.fontWeight = fonts.table_weight || "bold";
        valNode.style.color = fonts.table_color || "#000000";
        valNode.onclick = (e) => {
          e.stopPropagation();
          openTypoBar(r.key, `工单数值【${labelText}】`);
        };
      }

      leftGrid.appendChild(rowEl);
    });
  }
}

// Backward-compatible alias
function renderTemplateHeaderOverlay() {
  renderTableTexts();
}

// --- Floating Typography Inspector Bar ---
function openTypoBar(targetKey, displayName) {
  state.current_typo_target = targetKey;
  const bar = document.getElementById("floating-typography-bar");
  const nameEl = document.getElementById("typo-field-name");
  const contentInp = document.getElementById("typo-content-input");
  const fontSelect = document.getElementById("typo-font-family-select");
  const sizeInp = document.getElementById("typo-font-size-input");
  const boldBtn = document.getElementById("btn-typo-bold-toggle");
  const colorPicker = document.getElementById("typo-color-picker");

  if (!bar) return;
  nameEl.textContent = displayName || targetKey;
  bar.style.display = "block";

  const cfg = state.template_config || {};
  const fonts = cfg.fonts || {};
  const task = getActiveTask();

  // Determine current value
  let curVal = "";
  let fontPrefix = "table";

  if (targetKey === "title") {
    curVal = cfg.title || "臻兴科技开发样品单";
    fontPrefix = "title";
  } else if (targetKey === "category_title") {
    curVal = cfg.category_title || "成人女鞋";
    fontPrefix = "category";
  } else if (targetKey === "reviewer") {
    curVal = `${cfg.reviewer || "审核:"}  ${cfg.re_reviewer || "复核:"}`;
    fontPrefix = "table";
  } else if (targetKey.startsWith("label_")) {
    const lk = targetKey.replace("label_", "");
    curVal = cfg.labels?.[lk] || "";
    fontPrefix = "labels";
  } else if (task && targetKey in task) {
    curVal = task[targetKey] || "";
    fontPrefix = "table";
  }

  contentInp.value = curVal;
  const curFont = fonts[`${fontPrefix}_font`] || "Microsoft YaHei";
  fontSelect.value = curFont;
  sizeInp.value = fonts[`${fontPrefix}_size`] || 52;
  const isBold = (fonts[`${fontPrefix}_weight`] || "bold") === "bold";
  boldBtn.classList.toggle("active", isBold);
  colorPicker.value = fonts[`${fontPrefix}_color`] || "#000000";
}

function initTypographyInspector() {
  const bar = document.getElementById("floating-typography-bar");
  const closeBtn = document.getElementById("btn-close-typo-bar");
  const contentInp = document.getElementById("typo-content-input");
  const fontSelect = document.getElementById("typo-font-family-select");
  const sizeInp = document.getElementById("typo-font-size-input");
  const sizeDecBtn = document.getElementById("btn-typo-size-dec");
  const sizeIncBtn = document.getElementById("btn-typo-size-inc");
  const boldBtn = document.getElementById("btn-typo-bold-toggle");
  const colorPicker = document.getElementById("typo-color-picker");

  if (closeBtn && bar) {
    closeBtn.onclick = () => { bar.style.display = "none"; };
  }

  function getActiveFontPrefix() {
    const targetKey = state.current_typo_target;
    if (targetKey === "title") return "title";
    if (targetKey === "category_title") return "category";
    if (targetKey && targetKey.startsWith("label_")) return "labels";
    return "table";
  }

  if (contentInp) {
    contentInp.oninput = (e) => {
      const val = e.target.value;
      const targetKey = state.current_typo_target;
      if (!targetKey) return;
      const cfg = state.template_config;
      const task = getActiveTask();

      if (targetKey === "title") {
        cfg.title = val;
      } else if (targetKey === "category_title") {
        cfg.category_title = val;
      } else if (targetKey === "reviewer") {
        cfg.reviewer = val;
      } else if (targetKey.startsWith("label_")) {
        const lk = targetKey.replace("label_", "");
        if (!cfg.labels) cfg.labels = {};
        cfg.labels[lk] = val;
      } else if (task && targetKey in task) {
        task[targetKey] = val;
        const formInp = document.getElementById(`input-${targetKey}`);
        if (formInp) formInp.value = val;
      }
      renderTableTexts();
    };
  }

  if (fontSelect) {
    fontSelect.onchange = (e) => {
      const pfx = getActiveFontPrefix();
      if (!state.template_config.fonts) state.template_config.fonts = {};
      state.template_config.fonts[`${pfx}_font`] = e.target.value;
      renderTableTexts();
    };
  }

  function updateFontSize(val) {
    const num = Math.max(16, Math.min(140, parseInt(val) || 48));
    sizeInp.value = num;
    const pfx = getActiveFontPrefix();
    if (!state.template_config.fonts) state.template_config.fonts = {};
    state.template_config.fonts[`${pfx}_size`] = num;
    renderTableTexts();
  }

  if (sizeInp) {
    sizeInp.onchange = (e) => updateFontSize(e.target.value);
  }
  if (sizeDecBtn) {
    sizeDecBtn.onclick = () => updateFontSize(parseInt(sizeInp.value || 48) - 2);
  }
  if (sizeIncBtn) {
    sizeIncBtn.onclick = () => updateFontSize(parseInt(sizeInp.value || 48) + 2);
  }

  if (boldBtn) {
    boldBtn.onclick = () => {
      const pfx = getActiveFontPrefix();
      if (!state.template_config.fonts) state.template_config.fonts = {};
      const cur = state.template_config.fonts[`${pfx}_weight`] || "bold";
      const next = cur === "bold" ? "normal" : "bold";
      state.template_config.fonts[`${pfx}_weight`] = next;
      boldBtn.classList.toggle("active", next === "bold");
      renderTableTexts();
    };
  }

  if (colorPicker) {
    colorPicker.oninput = (e) => {
      const pfx = getActiveFontPrefix();
      if (!state.template_config.fonts) state.template_config.fonts = {};
      state.template_config.fonts[`${pfx}_color`] = e.target.value;
      renderTableTexts();
    };
  }
}

// --- Floating Line Style Inspector ---
function openLineBar() {
  const bar = document.getElementById("floating-line-style-bar");
  if (!bar) return;
  bar.style.display = "block";
  const cfg = state.template_config || {};
  const lines = cfg.lines || {};
  const bwSel = document.getElementById("line-border-width-select");
  const iwSel = document.getElementById("line-inner-width-select");
  const cp = document.getElementById("line-color-picker");
  const hex = document.getElementById("line-color-hex");
  const sl = document.getElementById("line-divider-slider");
  const ro = document.getElementById("line-divider-readout");

  if (bwSel) bwSel.value = String(lines.border_width || 4);
  if (iwSel) iwSel.value = String(lines.inner_width || 2);
  if (cp) cp.value = lines.border_color || "#000000";
  if (hex) hex.textContent = lines.border_color || "#000000";
  if (sl) sl.value = lines.divider_x || 840;
  if (ro) ro.textContent = `${lines.divider_x || 840}px`;
}

function initLineStyleInspector() {
  const bar = document.getElementById("floating-line-style-bar");
  const closeBtn = document.getElementById("btn-close-line-bar");
  const bwSel = document.getElementById("line-border-width-select");
  const iwSel = document.getElementById("line-inner-width-select");
  const cp = document.getElementById("line-color-picker");
  const hex = document.getElementById("line-color-hex");
  const sl = document.getElementById("line-divider-slider");
  const ro = document.getElementById("line-divider-readout");

  if (closeBtn && bar) {
    closeBtn.onclick = () => { bar.style.display = "none"; };
  }

  if (bwSel) {
    bwSel.onchange = (e) => {
      if (!state.template_config.lines) state.template_config.lines = {};
      state.template_config.lines.border_width = parseInt(e.target.value);
      renderTableVectorLines();
    };
  }

  if (iwSel) {
    iwSel.onchange = (e) => {
      if (!state.template_config.lines) state.template_config.lines = {};
      state.template_config.lines.inner_width = parseInt(e.target.value);
      renderTableVectorLines();
    };
  }

  if (cp) {
    cp.oninput = (e) => {
      const c = e.target.value;
      if (!state.template_config.lines) state.template_config.lines = {};
      state.template_config.lines.border_color = c;
      state.template_config.lines.inner_color = c;
      if (hex) hex.textContent = c;
      renderTableVectorLines();
    };
  }

  if (sl) {
    sl.oninput = (e) => {
      const val = parseInt(e.target.value);
      if (!state.template_config.lines) state.template_config.lines = {};
      state.template_config.lines.divider_x = val;
      if (ro) ro.textContent = `${val}px`;
      renderTableVectorLines();
      renderTableTexts();
    };
  }
}

function initTemplateEditor() {
  const btnToggle = document.getElementById("btn-toggle-edit-template");
  const headLogoBox = document.getElementById("stage-header-logo-box");
  const headLogoFileInp = document.getElementById("tmpl-logo-file-input");
  const btnOpenLineBar = document.getElementById("btn-open-line-bar");
  const btnSave = document.getElementById("btn-save-tmpl-header");
  const btnReset = document.getElementById("btn-reset-tmpl-header");
  const btnExit = document.getElementById("btn-exit-tmpl-header");
  const editBanner = document.getElementById("tmpl-edit-control-bar");

  function exitTemplateEdit() {
    state.is_editing_template = false;
    if (editBanner) editBanner.style.display = "none";
    const typoBar = document.getElementById("floating-typography-bar");
    if (typoBar) typoBar.style.display = "none";
    const lineBar = document.getElementById("floating-line-style-bar");
    if (lineBar) lineBar.style.display = "none";
    stage.classList.remove("template-editing");
    renderTableVectorLines();
    renderTableTexts();
  }

  if (btnToggle) {
    btnToggle.onclick = () => {
      state.is_editing_template = !state.is_editing_template;
      if (state.is_editing_template) {
        if (editBanner) editBanner.style.display = "flex";
        stage.classList.add("template-editing");
        showToast("✏️ 已进入底表模版编辑模式：点击任意文字更换字体/内容，点击调整线条修改网格");
      } else {
        exitTemplateEdit();
      }
    };
  }

  if (btnExit) btnExit.onclick = exitTemplateEdit;
  if (btnOpenLineBar) btnOpenLineBar.onclick = openLineBar;

  if (headLogoBox && headLogoFileInp) {
    headLogoBox.onclick = () => headLogoFileInp.click();
    headLogoFileInp.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      showLoading("正在上传并更换品牌主LOGO...");
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch("/api/template-config/upload-logo", { method: "POST", body: fd });
        const data = await res.json();
        if (data.status === "success") {
          state.template_config = data.config;
          renderTableTexts();
          showToast("📷 品牌主LOGO已更新！");
        } else {
          throw new Error(data.detail || "上传失败");
        }
      } catch (err) {
        alert("更换主LOGO失败: " + err.message);
      } finally {
        hideLoading();
        headLogoFileInp.value = "";
      }
    };
  }

  if (btnSave) {
    btnSave.onclick = async () => {
      showLoading("正在保存底表模版设置...");
      try {
        const res = await fetch("/api/template-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...state.template_config, is_custom: true })
        });
        const data = await res.json();
        if (data.status === "success") {
          state.template_config = data.config;
          exitTemplateEdit();
          showToast("💾 底表模版已保存！所有导出的送审图与PSD将自动应用该样式！");
        } else {
          throw new Error(data.detail || "保存失败");
        }
      } catch (err) {
        alert("保存模版失败: " + err.message);
      } finally {
        hideLoading();
      }
    };
  }

  if (btnReset) {
    btnReset.onclick = async () => {
      if (!confirm("确认恢复原版底表模版（navigare主标与臻兴科技、标准线条与字体）吗？")) return;
      showLoading("正在恢复默认模版...");
      try {
        const res = await fetch("/api/template-config/reset", { method: "POST" });
        const data = await res.json();
        if (data.status === "success") {
          state.template_config = data.config;
          exitTemplateEdit();
          showToast("↺ 已恢复原版底表模版！");
        } else {
          throw new Error(data.detail || "恢复失败");
        }
      } catch (err) {
        alert("恢复模版失败: " + err.message);
      } finally {
        hideLoading();
      }
    };
  }
}

// Backward-compatible alias for setupEventListeners
function initTemplateHeaderEditor() {
  initTemplateEditor();
  initTypographyInspector();
  initLineStyleInspector();
  setupLogoHubControls();
}

function setupLogoHubControls() {
  const catTabs = document.querySelectorAll(".logo-tab-btn");
  catTabs.forEach(btn => {
    btn.onclick = () => {
      catTabs.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.logo_category = btn.getAttribute("data-cat") || "all";
      renderLogoPool();
    };
  });

  const searchInp = document.getElementById("logo-search-input");
  if (searchInp) {
    searchInp.oninput = (e) => {
      state.logo_search_query = e.target.value;
      renderLogoPool();
    };
  }

  // Quick auto-align logos button in hub header
  const btnQuickAutoAlign = document.getElementById("btn-quick-auto-align-logos");
  if (btnQuickAutoAlign) {
    btnQuickAutoAlign.onclick = () => {
      const task = getActiveTask();
      if (!task || task.shoes.length === 0) {
        alert("当前还没有添加鞋款！");
        return;
      }
      autoLayoutLogosForAllShoes();
    };
  }

  // PDF import modal
  const btnOpenImport = document.getElementById("btn-open-import-pdf-modal");
  const modalImport = document.getElementById("modal-import-pdf");
  const btnCloseImport = document.getElementById("btn-close-import-pdf-modal");
  const btnCancelImport = document.getElementById("btn-cancel-import-pdf");
  const btnConfirmImport = document.getElementById("btn-confirm-import-pdf");
  const pdfPathInp = document.getElementById("input-pdf-path");

  if (btnOpenImport && modalImport) {
    btnOpenImport.onclick = () => modalImport.classList.add("show");
  }
  if (btnCloseImport && modalImport) {
    btnCloseImport.onclick = () => modalImport.classList.remove("show");
  }
  if (btnCancelImport && modalImport) {
    btnCancelImport.onclick = () => modalImport.classList.remove("show");
  }
  if (btnConfirmImport && modalImport) {
    btnConfirmImport.onclick = async () => {
      const pdfPath = pdfPathInp.value.trim();
      modalImport.classList.remove("show");
      showLoading("正在从 PDF 矢量手册高精提取标贴并自动入库...");
      try {
        const res = await fetch("/api/logos/import-pdf", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pdf_path: pdfPath || null })
        });
        const data = await res.json();
        if (data.status === "success") {
          await reloadLogosPool();
          showToast(`🎉 成功从 PDF 提取并导入 ${data.imported_count} 款矢量标贴！`);
        } else {
          throw new Error(data.detail || "提取导入失败");
        }
      } catch (err) {
        alert("导入 PDF 失败: " + err.message);
      } finally {
        hideLoading();
      }
    };
  }
}

// 极速暂存上传: 支持一次上传多个颜色照片，默认不强占CPU抠图，点击批量去底即可一键全部搞定！
async function handleFastRawUpload(fileList) {
  const task = getActiveTask();
  if (!task) return;

  const maxAllowed = 15;
  const currentCount = task.shoes.length;
  const availableSlots = maxAllowed - currentCount;

  if (availableSlots <= 0) {
    alert("每个款式最多支持 15 种颜色排版！");
    return;
  }

  const files = Array.from(fileList).slice(0, availableSlots);
  showLoading(`正在极速暂存原图（共 ${files.length} 张，支持录完颜色后批量去底）...`);

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/upload-raw", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (data.status === "success") {
        const idx = task.shoes.length;
        const color = DEFAULT_COLOR_PALETTE[idx % DEFAULT_COLOR_PALETTE.length] || `颜色${idx + 1}`;

        const autoLogos = [
          { logo_id: "logo_square_boat", file: "logos/logo_square_boat.png", rel_x: 0.35, rel_y: 0.06, scale: 1.0, rotation: 0 },
          { logo_id: "logo_nvg_cursive", file: "logos/logo_nvg_cursive.png", rel_x: 0.28, rel_y: 0.44, scale: 1.0, rotation: 0 }
        ];

        task.shoes.push({
          id: `shoe_${Date.now()}_${idx}`,
          color_name: color,
          raw_filename: data.raw_filename,
          raw_url: data.raw_url,
          cutout_filename: null,
          cutout_url: data.raw_url,
          is_cutout: false,
          width: data.width,
          height: data.height,
          offset_x: 0.0,
          offset_y: 0.0,
          scale_multiplier: 1.0,
          logos: autoLogos
        });
        state.selected_shoe_id = task.shoes[task.shoes.length - 1].id;

        if (data.was_downscaled) {
          showToast(`⚡ 原图(${data.orig_width}×${data.orig_height})超标，已自动等比例高清优化为(${data.width}×${data.height})，锁住细节并杜绝卡顿`);
        }
      }
    } catch (err) {
      console.error(err);
      alert(`第 ${i + 1} 张图片暂存失败：` + err.message);
    }
  }

  hideLoading();
  triggerAiAutoLayout();
  renderTasksNav();
  renderShoeListCards();
  syncGroupsToServer();
}

// 批量去底抠图 (离线嵌入式模型)
async function triggerBatchCutout() {
  const task = getActiveTask();
  if (!task) return;
  const unCutShoes = task.shoes.filter(s => !s.is_cutout);
  if (unCutShoes.length === 0) {
    alert("当前款式的所有照片均已完成离线 AI 抠图！");
    return;
  }

  showLoading(`正在启动本地内嵌 AI 批量去底（共 ${unCutShoes.length} 张）...`);
  const filenames = unCutShoes.map(s => s.raw_filename);

  try {
    const res = await fetch("/api/cutout-batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filenames })
    });
    const data = await res.json();
    if (data.status === "success") {
      data.results.forEach(r => {
        if (r.status === "success") {
          const target = task.shoes.find(s => s.raw_filename === r.raw_filename);
          if (target) {
            target.cutout_filename = r.cutout_filename;
            target.cutout_url = r.cutout_url;
            target.width = r.width;
            target.height = r.height;
            target.is_cutout = true;
          }
        }
      });
      showToast(`🎉 批量抠图完成！共处理 ${data.results.filter(r => r.status === "success").length} 张。`);
    }
  } catch (err) {
    console.error(err);
    alert("批量抠图发生异常：" + err.message);
  } finally {
    hideLoading();
    updateStageUI();
    renderTasksNav();
    renderShoeListCards();
    syncGroupsToServer();
  }
}

// AI 智能排版算法 (1 至 15 色精确网格划分与坐标求解)
function calculateAiSlots(count) {
  if (count <= 0) return [];

  const areaX1 = 950;
  const areaX2 = 3360;
  const areaY1 = 760;
  const areaY2 = 2360;
  const totalW = areaX2 - areaX1;
  const totalH = areaY2 - areaY1;

  if (count === 1) {
    return [{ cx: 2150, cy: 1480, max_w: 1400, max_h: 800, align: "center" }];
  } else if (count === 2) {
    return [
      { cx: 1550, cy: 1480, max_w: 1050, max_h: 650, align: "center" },
      { cx: 2750, cy: 1480, max_w: 1050, max_h: 650, align: "center" }
    ];
  } else if (count === 3) {
    return [
      { cx: 1550, cy: 1150, max_w: 1000, max_h: 560, align: "center" },
      { cx: 2750, cy: 1150, max_w: 1000, max_h: 560, align: "center" },
      { cx: 2150, cy: 1850, max_w: 1000, max_h: 560, align: "center" }
    ];
  } else if (count === 4) {
    return [
      { cx: 1510, cy: 1060, max_w: 1000, max_h: 530, align: "left" },
      { cx: 2720, cy: 1060, max_w: 1000, max_h: 530, align: "left" },
      { cx: 1510, cy: 1830, max_w: 1000, max_h: 530, align: "left" },
      { cx: 2720, cy: 1830, max_w: 1000, max_h: 530, align: "left" }
    ];
  }

  let rows, cols;
  if (count <= 6) {
    rows = 2; cols = 3;
  } else if (count <= 8) {
    rows = 2; cols = 4;
  } else if (count <= 9) {
    rows = 3; cols = 3;
  } else if (count <= 12) {
    rows = 3; cols = 4;
  } else {
    rows = 3; cols = 5;
  }

  const colW = totalW / cols;
  const rowH = totalH / rows;
  const maxW = Math.round(colW * 0.90);
  const maxH = Math.round(rowH * 0.72);

  const slots = [];
  for (let i = 0; i < count; i++) {
    const r = Math.floor(i / cols);
    const c = i % cols;
    const cx = Math.round(areaX1 + c * colW + colW / 2);
    const cy = Math.round(areaY1 + r * rowH + rowH / 2 - 20);
    slots.push({ cx, cy, max_w: maxW, max_h: maxH, align: "center" });
  }
  return slots;
}

function triggerAiAutoLayout() {
  const task = getActiveTask();
  if (!task) return;
  task.shoes.forEach(shoe => {
    shoe.offset_x = 0;
    shoe.offset_y = 0;
    shoe.scale_multiplier = 1.0;
  });
  updateStageUI();
  showToast("✨ AI 已自动计算最佳均分网格！");
  syncGroupsToServer();
}

function updateStageUI() {
  const task = getActiveTask();
  if (!task) return;

  // 0. Update Vector Lines & Text Layers
  renderTableVectorLines();
  renderTableTexts();

  // 2. Dynamic Shoes & Logos Layer
  stageShoesLayer.innerHTML = "";
  const count = task.shoes.length;
  document.getElementById("shoe-count-tag").textContent = `${count} / 15 款`;
  document.getElementById("canvas-shoe-count-hint").textContent = `${count} 色`;

  if (count === 0) return;

  const slots = calculateAiSlots(count);

  let colorFontSize = 58;
  if (count > 12) colorFontSize = 32;
  else if (count > 8) colorFontSize = 38;
  else if (count > 4) colorFontSize = 46;

  task.shoes.slice(0, slots.length).forEach((shoe, idx) => {
    const slot = slots[idx];
    const isSelected = shoe.id === state.selected_shoe_id;

    const baseFitScale = Math.min(slot.max_w / shoe.width, slot.max_h / shoe.height);
    const finalShoeScale = baseFitScale * (shoe.scale_multiplier ?? 1.0);
    const shoeW = Math.round(shoe.width * finalShoeScale);
    const shoeH = Math.round(shoe.height * finalShoeScale);
    
    const shoeX = Math.round(slot.cx - shoeW / 2 + (shoe.offset_x ?? 0.0));
    const shoeY = Math.round(slot.cy - shoeH / 2 + (shoe.offset_y ?? 0.0));

    const shoeEl = document.createElement("div");
    shoeEl.className = `stage-shoe-wrapper ${isSelected ? "selected" : ""}`;
    shoeEl.style.left = `${toStagePx(shoeX)}px`;
    shoeEl.style.top = `${toStagePx(shoeY)}px`;
    shoeEl.style.width = `${toStagePx(shoeW)}px`;
    shoeEl.style.height = `${toStagePx(shoeH)}px`;

    // Shoe image
    const imgEl = document.createElement("img");
    imgEl.src = shoe.is_cutout ? shoe.cutout_url : shoe.raw_url;
    imgEl.className = "stage-shoe-img";
    shoeEl.appendChild(imgEl);

    // Selected Shoe Floating Toolbar (换图、规整、缩放、删除)
    if (isSelected) {
      const shoeTb = document.createElement("div");
      shoeTb.className = "stage-shoe-toolbar";
      shoeTb.innerHTML = `
        <button class="shoe-tb-btn btn-shoe-replace" title="替换该鞋款照片（保留颜色名称）">🔄 换图</button>
        <button class="shoe-tb-btn btn-shoe-align-logos" title="智能规整此鞋上的所有标贴">🏷️ 规整标贴</button>
        <button class="shoe-tb-btn btn-shoe-scale-up" title="放大此鞋">➕</button>
        <button class="shoe-tb-btn btn-shoe-scale-down" title="缩小此鞋">➖</button>
        <button class="shoe-tb-btn danger btn-shoe-del" title="从送审单中删除此鞋">🗑️ 删除</button>
      `;

      shoeTb.querySelector(".btn-shoe-replace").onclick = (e) => {
        e.stopPropagation();
        state.replacing_shoe_id = shoe.id;
        const fi = document.getElementById("shoe-replace-file-input");
        if (fi) { fi.value = ""; fi.click(); }
      };

      shoeTb.querySelector(".btn-shoe-align-logos").onclick = (e) => {
        e.stopPropagation();
        autoLayoutShoeLogos(shoe);
        updateStageUI();
        syncGroupsToServer();
        showToast(`🏷️ 已智能规整【${shoe.color_name || '当前鞋款'}】上的所有标贴！`);
      };

      shoeTb.querySelector(".btn-shoe-scale-up").onclick = (e) => {
        e.stopPropagation();
        shoe.scale_multiplier = Math.min(2.5, (shoe.scale_multiplier ?? 1.0) + 0.1);
        updateStageUI();
      };

      shoeTb.querySelector(".btn-shoe-scale-down").onclick = (e) => {
        e.stopPropagation();
        shoe.scale_multiplier = Math.max(0.4, (shoe.scale_multiplier ?? 1.0) - 0.1);
        updateStageUI();
      };

      shoeTb.querySelector(".btn-shoe-del").onclick = (e) => {
        e.stopPropagation();
        const idxInTask = task.shoes.findIndex(s => s.id === shoe.id);
        if (idxInTask >= 0) {
          task.shoes.splice(idxInTask, 1);
          if (state.selected_shoe_id === shoe.id) {
            state.selected_shoe_id = task.shoes[0] ? task.shoes[0].id : null;
          }
          triggerAiAutoLayout();
          renderShoeListCards();
          renderTasksNav();
          syncGroupsToServer();
          showToast(`🗑️ 已删除鞋款【${shoe.color_name || '未命名'}】`);
        }
      };

      shoeEl.appendChild(shoeTb);
    }

    // Click to select
    shoeEl.onclick = (e) => {
      e.stopPropagation();
      state.selected_shoe_id = shoe.id;
      updateStageUI();
      renderShoeListCards();
    };

    // Drag to Move Shoe with Smart Alignment Guides
    makeShoeDraggable(shoeEl, shoe, idx, slots);

    // Mouse wheel to scale shoe
    shoeEl.onwheel = (e) => {
      e.preventDefault();
      e.stopPropagation();
      const step = e.deltaY < 0 ? 0.06 : -0.06;
      shoe.scale_multiplier = Math.max(0.4, Math.min(2.5, (shoe.scale_multiplier ?? 1.0) + step));
      updateStageUI();
    };

    // Render Logos
    shoe.logos.forEach((logo, lIdx) => {
      const logoEl = document.createElement("div");
      logoEl.className = "stage-logo-element";
      
      const logoW = Math.round(180 * logo.scale * (finalShoeScale / 0.5));
      const logoH = Math.round(140 * logo.scale * (finalShoeScale / 0.5));
      
      logoEl.style.left = `${Math.round(logo.rel_x * 100)}%`;
      logoEl.style.top = `${Math.round(logo.rel_y * 100)}%`;
      logoEl.style.width = `${toStagePx(logoW)}px`;
      logoEl.style.height = `${toStagePx(logoH)}px`;
      if (logo.rotation) {
        logoEl.style.transform = `rotate(${logo.rotation}deg)`;
      }

      const lImg = document.createElement("img");
      const logoDef = state.logos_pool.find(l => l.id === logo.logo_id);
      const fName = logo.file || (logoDef ? logoDef.file : "logos/logo_square_boat.png");
      const imgUrl = fName.startsWith("/") ? fName : `/static/assets/${fName}`;
      lImg.src = imgUrl;
      lImg.style.width = "100%";
      lImg.style.height = "100%";
      lImg.style.objectFit = "contain";
      lImg.style.pointerEvents = "none";
      logoEl.appendChild(lImg);

      // Mini-action buttons (包含 🔄 快捷换标)
      const actBar = document.createElement("div");
      actBar.style.position = "absolute";
      actBar.style.top = "-22px";
      actBar.style.left = "0";
      actBar.style.display = "flex";
      actBar.style.gap = "2px";
      actBar.innerHTML = `
        <button class="qz-btn qz-btn-secondary qz-btn-sm" title="放大标贴" style="padding:1px 3px;font-size:8px;">➕</button>
        <button class="qz-btn qz-btn-secondary qz-btn-sm" title="缩小标贴" style="padding:1px 3px;font-size:8px;">➖</button>
        <button class="qz-btn qz-btn-secondary qz-btn-sm" title="旋转15度" style="padding:1px 3px;font-size:8px;">↻</button>
        <button class="qz-btn qz-btn-secondary qz-btn-sm" title="切换标贴样式" style="padding:1px 3px;font-size:8px;">🔄</button>
        <button class="qz-btn qz-btn-danger qz-btn-sm" title="删除标贴" style="padding:1px 3px;font-size:8px;">✕</button>
      `;
      const [btnP, btnM, btnR, btnSwap, btnD] = actBar.children;
      btnP.onclick = (e) => { e.stopPropagation(); logo.scale = Math.min(3.0, logo.scale + 0.1); updateStageUI(); };
      btnM.onclick = (e) => { e.stopPropagation(); logo.scale = Math.max(0.2, logo.scale - 0.1); updateStageUI(); };
      btnR.onclick = (e) => { e.stopPropagation(); logo.rotation = ((logo.rotation || 0) + 15) % 360; updateStageUI(); };
      btnSwap.onclick = (e) => {
        e.stopPropagation();
        if (state.logos_pool.length === 0) return;
        const curIdx = state.logos_pool.findIndex(l => l.id === logo.logo_id);
        const next = state.logos_pool[(curIdx + 1) % state.logos_pool.length];
        logo.logo_id = next.id;
        logo.file = next.file;
        updateStageUI();
        syncGroupsToServer();
        showToast(`🔄 标贴已切换为【${next.name}】`);
      };
      btnD.onclick = (e) => {
        e.stopPropagation();
        shoe.logos.splice(lIdx, 1);
        updateStageUI();
        syncGroupsToServer();
        showToast("🗑️ 已删除标贴");
      };
      logoEl.appendChild(actBar);

      makeLogoDraggable(logoEl, logo, shoeW, shoeH);

      logoEl.onwheel = (e) => {
        e.preventDefault();
        e.stopPropagation();
        logo.scale = e.deltaY < 0 ? Math.min(3.0, logo.scale + 0.08) : Math.max(0.2, logo.scale - 0.08);
        updateStageUI();
      };

      shoeEl.appendChild(logoEl);
    });

    stageShoesLayer.appendChild(shoeEl);

    // Color Name Text
    if (shoe.color_name) {
      const colorTextEl = document.createElement("div");
      colorTextEl.className = "dyn-text";
      colorTextEl.style.fontSize = `${toStagePx(colorFontSize)}px`;
      colorTextEl.textContent = shoe.color_name;
      colorTextEl.style.cursor = "pointer";
      colorTextEl.title = "点击快速修改颜色名称";

      const labelPosY = shoeY + shoeH + (count > 6 ? 16 : 28);
      colorTextEl.style.left = `${toStagePx(shoeX + shoeW / 2)}px`;
      colorTextEl.style.top = `${toStagePx(labelPosY)}px`;
      colorTextEl.style.transform = "translateX(-50%)";

      colorTextEl.onclick = () => {
        const newVal = prompt("请输入颜色名称：", shoe.color_name);
        if (newVal !== null) {
          shoe.color_name = newVal.trim();
          updateStageUI();
          renderShoeListCards();
          syncGroupsToServer();
        }
      };

      stageShoesLayer.appendChild(colorTextEl);
    }
  });
}

// --- Smart Dragging & Alignment Snapping Guides ---

function makeShoeDraggable(shoeEl, shoe, slotIndex, slots) {
  let isDragging = false;
  let startX = 0, startY = 0;
  let initX = shoe.offset_x ?? 0.0;
  let initY = shoe.offset_y ?? 0.0;
  const guidesLayer = document.getElementById("stage-guides-layer");

  shoeEl.addEventListener("mousedown", (e) => {
    if (e.target.closest(".stage-logo-element") || e.target.closest(".stage-shoe-toolbar")) return;
    e.preventDefault();
    isDragging = true;
    startX = e.clientX;
    startY = e.clientY;
    initX = shoe.offset_x ?? 0.0;
    initY = shoe.offset_y ?? 0.0;

    const task = getActiveTask();
    const curSlot = slots[slotIndex];

    const onMouseMove = (ev) => {
      if (!isDragging) return;
      const dx = (ev.clientX - startX) / state.stage_scale;
      const dy = (ev.clientY - startY) / state.stage_scale;
      
      let targetOffsetX = Math.round(initX + dx);
      let targetOffsetY = Math.round(initY + dy);

      // Current shoe bounding box in 3508x2480 space
      const baseFitScale = Math.min(curSlot.max_w / shoe.width, curSlot.max_h / shoe.height);
      const finalShoeScale = baseFitScale * (shoe.scale_multiplier ?? 1.0);
      const shoeW = Math.round(shoe.width * finalShoeScale);
      const shoeH = Math.round(shoe.height * finalShoeScale);

      let curCX = curSlot.cx + targetOffsetX;
      let curCY = curSlot.cy + targetOffsetY;
      let curX1 = curCX - shoeW / 2;
      let curX2 = curCX + shoeW / 2;
      let curY1 = curCY - shoeH / 2;
      let curY2 = curCY + shoeH / 2;

      // Smart Alignment Snapping with other shoes
      const SNAP_THRESHOLD = 18;
      let svgLines = [];

      // Check alignment with canvas drawing area center
      const CANVAS_CX = 2155;
      const CANVAS_CY = 1560;
      if (Math.abs(curCX - CANVAS_CX) < SNAP_THRESHOLD) {
        targetOffsetX = CANVAS_CX - curSlot.cx;
        curCX = CANVAS_CX;
        svgLines.push({
          x1: CANVAS_CX, y1: 760, x2: CANVAS_CX, y2: 2360,
          label: "画布水平居中", lx: CANVAS_CX + 10, ly: 820
        });
      }
      if (Math.abs(curCY - CANVAS_CY) < SNAP_THRESHOLD) {
        targetOffsetY = CANVAS_CY - curSlot.cy;
        curCY = CANVAS_CY;
        svgLines.push({
          x1: 950, y1: CANVAS_CY, x2: 3360, y2: CANVAS_CY,
          label: "画布垂直居中", lx: 1000, ly: CANVAS_CY - 10
        });
      }

      // Check against all other shoes
      task.shoes.forEach((otherShoe, oIdx) => {
        if (otherShoe.id === shoe.id || oIdx >= slots.length) return;
        const oSlot = slots[oIdx];
        const oFitScale = Math.min(oSlot.max_w / otherShoe.width, oSlot.max_h / otherShoe.height);
        const oFinalScale = oFitScale * (otherShoe.scale_multiplier ?? 1.0);
        const oW = Math.round(otherShoe.width * oFinalScale);
        const oH = Math.round(otherShoe.height * oFinalScale);

        const oCX = Math.round(oSlot.cx + (otherShoe.offset_x ?? 0.0));
        const oCY = Math.round(oSlot.cy + (otherShoe.offset_y ?? 0.0));
        const oX1 = oCX - oW / 2;
        const oX2 = oCX + oW / 2;
        const oY1 = oCY - oH / 2;
        const oY2 = oCY + oH / 2;

        // X-Center Align
        if (Math.abs(curCX - oCX) < SNAP_THRESHOLD) {
          targetOffsetX = oCX - curSlot.cx;
          curCX = oCX;
          const minY = Math.min(curCY, oCY) - 100;
          const maxY = Math.max(curCY, oCY) + 100;
          svgLines.push({
            x1: oCX, y1: minY, x2: oCX, y2: maxY,
            label: "垂直列对齐", lx: oCX + 12, ly: (minY + maxY) / 2
          });
        }
        // X-Left Align
        else if (Math.abs(curX1 - oX1) < SNAP_THRESHOLD) {
          targetOffsetX = (oX1 + shoeW / 2) - curSlot.cx;
          curX1 = oX1;
          const minY = Math.min(curY1, oY1) - 60;
          const maxY = Math.max(curY2, oY2) + 60;
          svgLines.push({
            x1: oX1, y1: minY, x2: oX1, y2: maxY,
            label: "左边缘对齐", lx: oX1 + 12, ly: (minY + maxY) / 2
          });
        }

        // Y-Center Align (Horizontal Alignment)
        if (Math.abs(curCY - oCY) < SNAP_THRESHOLD) {
          targetOffsetY = oCY - curSlot.cy;
          curCY = oCY;
          const minX = Math.min(curCX, oCX) - 100;
          const maxX = Math.max(curCX, oCX) + 100;
          svgLines.push({
            x1: minX, y1: oCY, x2: maxX, y2: oCY,
            label: "水平排对齐", lx: (minX + maxX) / 2 - 40, ly: oCY - 12
          });
        }
        // Y-Bottom Align (大底基准线对齐)
        else if (Math.abs(curY2 - oY2) < SNAP_THRESHOLD) {
          targetOffsetY = (oY2 - shoeH / 2) - curSlot.cy;
          curY2 = oY2;
          const minX = Math.min(curX1, oX1) - 60;
          const maxX = Math.max(curX2, oX2) + 60;
          svgLines.push({
            x1: minX, y1: oY2, x2: maxX, y2: oY2,
            label: "底边平齐", lx: (minX + maxX) / 2 - 40, ly: oY2 + 24
          });
        }
      });

      shoe.offset_x = targetOffsetX;
      shoe.offset_y = targetOffsetY;
      updateStageUI();

      // Render guides into SVG
      if (guidesLayer) {
        if (svgLines.length === 0) {
          guidesLayer.innerHTML = "";
        } else {
          guidesLayer.innerHTML = svgLines.map(l => `
            <line x1="${l.x1}" y1="${l.y1}" x2="${l.x2}" y2="${l.y2}" stroke="#10b981" stroke-width="3" stroke-dasharray="10,6" />
            <rect x="${l.lx - 6}" y="${l.ly - 20}" width="110" height="26" rx="4" fill="rgba(16, 185, 129, 0.9)" />
            <text x="${l.lx + 4}" y="${l.ly - 3}" fill="#ffffff" font-size="16" font-weight="bold" font-family="Microsoft YaHei">${l.label}</text>
          `).join("");
        }
      }
    };

    const onMouseUp = () => {
      isDragging = false;
      if (guidesLayer) guidesLayer.innerHTML = "";
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      syncGroupsToServer();
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  });
}

function makeLogoDraggable(logoEl, logo, shoeW, shoeH) {
  let isDragging = false;
  let startX = 0, startY = 0;
  let startRelX = logo.rel_x, startRelY = logo.rel_y;

  logoEl.addEventListener("mousedown", (e) => {
    if (e.target.tagName === "BUTTON") return;
    e.stopPropagation();
    e.preventDefault();
    isDragging = true;
    startX = e.clientX;
    startY = e.clientY;
    startRelX = logo.rel_x;
    startRelY = logo.rel_y;

    const onMouseMove = (ev) => {
      if (!isDragging) return;
      const curScale = state.stage_scale || 1.0;
      const dx = (ev.clientX - startX) / curScale;
      const dy = (ev.clientY - startY) / curScale;

      logo.rel_x = Math.max(-0.4, Math.min(1.4, startRelX + dx / shoeW));
      logo.rel_y = Math.max(-0.4, Math.min(1.4, startRelY + dy / shoeH));
      logoEl.style.left = `${Math.round(logo.rel_x * 100)}%`;
      logoEl.style.top = `${Math.round(logo.rel_y * 100)}%`;
    };

    const onMouseUp = () => {
      isDragging = false;
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      updateStageUI();
      syncGroupsToServer();
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  });
}

// --- Render Shoe List Cards inside Bottom Drawer (1~15 Colors) ---

function renderShoeListCards() {
  const task = getActiveTask();
  const list = document.getElementById("shoe-list");
  if (!list) return;
  list.innerHTML = "";
  if (!task) return;

  task.shoes.forEach((shoe, idx) => {
    const isSelected = shoe.id === state.selected_shoe_id;
    const card = document.createElement("div");
    card.className = `shoe-color-card ${isSelected ? "selected" : ""}`;
    card.onclick = () => {
      state.selected_shoe_id = shoe.id;
      updateStageUI();
      renderShoeListCards();
    };

    const statusBadge = shoe.is_cutout 
      ? '<span class="shoe-status-chip cutout-done">✅ 已去底</span>' 
      : '<span class="shoe-status-chip">⏳ 待去底</span>';

    card.innerHTML = `
      <div class="shoe-thumb-box">
        <img src="${shoe.is_cutout ? shoe.cutout_url : shoe.raw_url}" class="shoe-thumb-img" alt="Shoe">
        ${statusBadge}
      </div>
      <div class="shoe-card-footer">
        <input type="text" class="shoe-color-input" value="${shoe.color_name}" placeholder="颜色">
        <div class="shoe-card-actions">
          <button class="shoe-action-btn shoe-replace-btn" title="替换鞋款照片（保留颜色名称）">🔄 换图</button>
          <button class="shoe-del-btn" title="删除该颜色">🗑️</button>
        </div>
      </div>
    `;

    const input = card.querySelector(".shoe-color-input");
    input.onclick = (e) => e.stopPropagation();
    input.oninput = (e) => {
      shoe.color_name = e.target.value;
      updateStageUI();
      syncGroupsToServer();
    };

    const btnReplace = card.querySelector(".shoe-replace-btn");
    btnReplace.onclick = (e) => {
      e.stopPropagation();
      state.replacing_shoe_id = shoe.id;
      const fi = document.getElementById("shoe-replace-file-input");
      if (fi) {
        fi.value = "";
        fi.click();
      }
    };

    const delBtn = card.querySelector(".shoe-del-btn");
    delBtn.onclick = (e) => {
      e.stopPropagation();
      task.shoes.splice(idx, 1);
      if (state.selected_shoe_id === shoe.id) {
        state.selected_shoe_id = task.shoes[0]?.id ?? null;
      }
      triggerAiAutoLayout();
      renderShoeListCards();
      renderTasksNav();
      syncGroupsToServer();
    };

    list.appendChild(card);
  });
}

// 导出当前送审大图 (300DPI)
async function renderAndExportCurrent(isSilent = false) {
  const task = getActiveTask();
  if (!task || task.shoes.length === 0) {
    if (!isSilent) alert("当前款式尚未添加鞋子照片！");
    return null;
  }

  showLoading(`正在生成【${task.name}】300DPI 审版大图 (自动调用离线 AI 抠图引擎)...`);

  const payload = {
    id: task.id,
    name: task.name,
    sku: task.sku,
    material_code: task.material_code,
    season: task.season,
    craft: task.craft,
    category: task.category,
    size: task.size,
    fabrics: task.fabrics,
    soles: task.soles,
    shoes: task.shoes.map(s => ({
      id: s.id,
      color_name: s.color_name,
      raw_filename: s.raw_filename,
      cutout_filename: s.cutout_filename,
      is_cutout: s.is_cutout,
      offset_x: s.offset_x ?? 0.0,
      offset_y: s.offset_y ?? 0.0,
      scale_multiplier: s.scale_multiplier ?? 1.0,
      logos: s.logos.map(l => ({
        logo_id: l.logo_id,
        rel_x: l.rel_x,
        rel_y: l.rel_y,
        scale: l.scale,
        rotation: l.rotation
      }))
    }))
  };

  try {
    const res = await fetch("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === "success") {
      task.shoes.forEach(s => s.is_cutout = true);
      renderTasksNav();
      renderShoeListCards();
      syncGroupsToServer();

      if (!isSilent) {
        hideLoading();
        // 自动触发 300DPI JPG 送审图下载
        const aJpg = document.createElement("a");
        aJpg.href = data.download_url;
        aJpg.download = data.filename;
        document.body.appendChild(aJpg);
        aJpg.click();
        document.body.removeChild(aJpg);

        // 如果生成了可编辑分层 PSD，也自动触发下载
        if (data.has_psd && data.psd_download_url) {
          const aPsd = document.createElement("a");
          aPsd.href = data.psd_download_url;
          aPsd.download = data.psd_filename;
          document.body.appendChild(aPsd);
          setTimeout(() => {
            aPsd.click();
            document.body.removeChild(aPsd);
          }, 350);
        }

        setTimeout(() => {
          const psdTip = data.has_psd ? `\n2. 🎨 Photoshop 100% 可编辑分层工程 (${data.psd_filename})` : '';
          const msg = `🎉【${task.name}】审版图稿已全量输出！\n\n已为您同步输出：\n1. 🖼️ 300DPI 印刷送审大图 (${data.filename})${psdTip}\n\n保存在：\n${data.filepath}\n\n是否立即打开成品文件夹？`;
          if (confirm(msg)) {
            openOutputFolder();
          }
        }, 600);
      }
      return data;
    } else {
      throw new Error(data.detail || "生成失败");
    }
  } catch (err) {
    console.error(err);
    if (!isSilent) alert("生成失败：" + err.message);
    return null;
  } finally {
    if (!isSilent) hideLoading();
  }
}

// 批量导出当前批次下的所有款式任务
async function batchRenderActiveGroup() {
  const group = getActiveGroup();
  if (!group || !group.tasks) return;

  const readyTasks = group.tasks.filter(t => t.shoes.length > 0);
  if (readyTasks.length === 0) {
    alert(`当前标签【${group.name}】下没有任何包含鞋子照片的款式！请先添加照片。`);
    return;
  }

  showLoading(`正在批量导出当前标签【${group.name}】的 ${readyTasks.length} 个款式审版图稿...`);

  const payload = {
    tasks: readyTasks.map(task => ({
      id: task.id,
      name: task.name,
      sku: task.sku,
      material_code: task.material_code,
      season: task.season,
      craft: task.craft,
      category: task.category,
      size: task.size,
      fabrics: task.fabrics,
      soles: task.soles,
      shoes: task.shoes.map(s => ({
        id: s.id,
        color_name: s.color_name,
        raw_filename: s.raw_filename,
        cutout_filename: s.cutout_filename,
        is_cutout: s.is_cutout,
        offset_x: s.offset_x ?? 0.0,
        offset_y: s.offset_y ?? 0.0,
        scale_multiplier: s.scale_multiplier ?? 1.0,
        logos: s.logos.map(l => ({
          logo_id: l.logo_id,
          rel_x: l.rel_x,
          rel_y: l.rel_y,
          scale: l.scale,
          rotation: l.rotation
        }))
      }))
    }))
  };

  try {
    const res = await fetch("/api/batch-render-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === "success") {
      hideLoading();
      readyTasks.forEach(t => t.shoes.forEach(s => s.is_cutout = true));
      renderTasksNav();
      renderShoeListCards();
      syncGroupsToServer();

      alert(`🎉 批量导出完成！标签【${group.name}】共输出 ${data.results.length} 款图稿！\n已为您每款同时生成了 300DPI 审版大图 (JPG) 与 Photoshop 可编辑分层工程 (PSD)！\n即将打开成品文件夹。`);
      openOutputFolder();
    }
  } catch (err) {
    console.error(err);
    alert("批量生成失败：" + err.message);
  } finally {
    hideLoading();
  }
}

async function openOutputFolder() {
  try {
    await fetch("/api/open-folder");
  } catch (err) {
    console.error(err);
  }
}

function showLoading(msg) {
  loadingText.textContent = msg;
  loadingModal.classList.add("show");
}

function hideLoading() {
  loadingModal.classList.remove("show");
}

function showToast(msg) {
  const toast = document.getElementById("global-toast");
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 3200);
}
