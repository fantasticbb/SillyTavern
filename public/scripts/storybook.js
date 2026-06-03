import { uuidv4, escapeHtml } from './utils.js';
import { getRequestHeaders, characters, main_api } from '../script.js';
import { oai_settings, getChatCompletionModel } from './openai.js';

const STORYBOOK_DIR = '/api/storybook';

let currentStorybook = null;
let currentStorybookName = null;
let selectedNodeId = null;

export function initStorybook() {
    $('#StorybookDrawerIcon').on('click', () => {
        if ($('#StorybookPanel').hasClass('openDrawer')) {
            loadStorybookList();
        }
    });

    $('#storybook_panel_pin').on('click', function () {
        if ($(this).prop('checked')) {
            $('#StorybookPanel').addClass('pinnedOpen');
        } else {
            $('#StorybookPanel').removeClass('pinnedOpen');
        }
    });

    $('#storybook_create_button').on('click', createStorybook);
    $('#storybook_selector').on('change', onStorybookSelect);
    $('#storybook_delete_button').on('click', deleteStorybook);
    $('#storybook_rename_button').on('click', renameStorybook);
    $('#storybook_duplicate_button').on('click', duplicateStorybook);
    $('#storybook_add_node').on('click', addNewNode);
    $('#storybook_node_save').on('click', saveCurrentNode);
    $('#storybook_node_delete').on('click', deleteCurrentNode);
    $('#storybook_node_generate').on('click', generateNodeContent);
    $('#storybook_add_connection').on('click', addConnection);

    $('#storybook_node_characters').on('click', () => { showCharacterPicker(); });
    $('#storybook_node_characters').on('dragover', function (e) {
        e.preventDefault();
        $(this).addClass('drag-over');
    });
    $('#storybook_node_characters').on('dragleave', function () {
        $(this).removeClass('drag-over');
    });
    $('#storybook_node_characters').on('drop', function (e) {
        e.preventDefault();
        $(this).removeClass('drag-over');
        const charData = e.originalEvent.dataTransfer.getData('text/plain');
        if (charData) {
            try {
                const char = JSON.parse(charData);
                addCharacterToNode(char);
            } catch (err) {
                // ignore
            }
        }
    });

    $('#storybook_node_title').on('input', debounceNodeAutoSave);
    $('#storybook_node_description').on('input', debounceNodeAutoSave);

    loadStorybookList();
}

async function loadStorybookList() {
    try {
        const response = await fetch(`${STORYBOOK_DIR}/list`, {
            method: 'POST',
            headers: getRequestHeaders(),
        });
        const data = await response.json();
        const select = $('#storybook_selector');
        select.find('option:not(:first)').remove();
        for (const item of data) {
            select.append(`<option value="${escapeHtml(item.file_id)}">${escapeHtml(item.name)} (${item.node_count} nodes)</option>`);
        }
    } catch (err) {
        console.error('Failed to load storybook list:', err);
    }
}

async function createStorybook() {
    const name = prompt('Enter story book name:');
    if (!name) return;

    const data = {
        name: name,
        description: '',
        nodes: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
    };

    try {
        const response = await fetch(`${STORYBOOK_DIR}/save`, {
            method: 'POST',
            headers: getRequestHeaders(),
            body: JSON.stringify({ name: name, data: data }),
        });
        if (response.ok) {
            await loadStorybookList();
            $('#storybook_selector').val(getSanitizedFilename(name));
            await loadStorybook(getSanitizedFilename(name));
        }
    } catch (err) {
        console.error('Failed to create storybook:', err);
    }
}

function getSanitizedFilename(name) {
    return name.replace(/[^a-zA-Z0-9\u4e00-\u9fff _-]/g, '_');
}

async function onStorybookSelect() {
    const name = $(this).val();
    if (!name) {
        closeEditor();
        return;
    }
    await loadStorybook(name);
}

async function loadStorybook(name) {
    try {
        const response = await fetch(`${STORYBOOK_DIR}/get`, {
            method: 'POST',
            headers: getRequestHeaders(),
            body: JSON.stringify({ name: name }),
        });
        if (!response.ok) {
            toastr.error('Failed to load storybook');
            return;
        }
        currentStorybook = await response.json();
        currentStorybookName = name;
        selectedNodeId = null;
        renderTimeline();
        $('#storybook_editor').show();
        $('#storybook_node_editor').hide();
        $('#storybook_generated_content').hide();
    } catch (err) {
        console.error('Failed to load storybook:', err);
    }
}

function closeEditor() {
    currentStorybook = null;
    currentStorybookName = null;
    selectedNodeId = null;
    $('#storybook_editor').hide();
    $('#storybook_node_editor').hide();
    $('#storybook_generated_content').hide();
    $('#storybook_timeline').empty();
}

async function deleteStorybook() {
    if (!currentStorybookName) return;
    if (!confirm(`Delete story book "${currentStorybook?.name || currentStorybookName}"?`)) return;

    try {
        await fetch(`${STORYBOOK_DIR}/delete`, {
            method: 'POST',
            headers: getRequestHeaders(),
            body: JSON.stringify({ name: currentStorybookName }),
        });
        closeEditor();
        await loadStorybookList();
    } catch (err) {
        console.error('Failed to delete storybook:', err);
    }
}

async function renameStorybook() {
    if (!currentStorybookName) return;
    const newName = prompt('Enter new name:', currentStorybook?.name || currentStorybookName);
    if (!newName || newName === currentStorybookName) return;

    try {
        const response = await fetch(`${STORYBOOK_DIR}/rename`, {
            method: 'POST',
            headers: getRequestHeaders(),
            body: JSON.stringify({ oldName: currentStorybookName, newName: newName }),
        });
        if (response.ok) {
            currentStorybook.name = newName;
            currentStorybookName = getSanitizedFilename(newName);
            await loadStorybookList();
        }
    } catch (err) {
        console.error('Failed to rename storybook:', err);
    }
}

async function duplicateStorybook() {
    if (!currentStorybookName) return;
    try {
        await fetch(`${STORYBOOK_DIR}/duplicate`, {
            method: 'POST',
            headers: getRequestHeaders(),
            body: JSON.stringify({ name: currentStorybookName }),
        });
        await loadStorybookList();
        toastr.success('Story book duplicated');
    } catch (err) {
        console.error('Failed to duplicate storybook:', err);
    }
}

function renderTimeline() {
    const container = $('#storybook_timeline');
    container.empty();

    if (!currentStorybook?.nodes?.length) return;

    const nodes = [...currentStorybook.nodes].sort((a, b) => (a.position || 0) - (b.position || 0));

    for (const node of nodes) {
        const nodeEl = $(`
            <div class="storybook_timeline_node" data-node-id="${node.id}">
                <div class="storybook_timeline_dot"></div>
                <div class="storybook_timeline_node_label">${escapeHtml(node.title || 'Untitled')}</div>
                <div class="storybook_timeline_node_icons"></div>
            </div>
        `);

        if (node.id === selectedNodeId) {
            nodeEl.addClass('active');
        }

        const iconsContainer = nodeEl.find('.storybook_timeline_node_icons');
        if (Array.isArray(node.characters)) {
            for (const char of node.characters) {
                const charData = findCharacterByName(char.name);
                if (charData?.avatar_url) {
                    iconsContainer.append(`<img src="${escapeHtml(charData.avatar_url)}" title="${escapeHtml(char.name)}" alt="${escapeHtml(char.name)}">`);
                } else {
                    iconsContainer.append(`<i class="fa-solid fa-user" title="${escapeHtml(char.name)}"></i>`);
                }
            }
        }

        nodeEl.on('click', () => selectNode(node.id));
        container.append(nodeEl);
    }
}

function selectNode(nodeId) {
    selectedNodeId = nodeId;
    const node = currentStorybook?.nodes?.find(n => n.id === nodeId);
    if (!node) return;

    $('#storybook_timeline .storybook_timeline_node').removeClass('active');
    $(`.storybook_timeline_node[data-node-id="${nodeId}"]`).addClass('active');

    $('#storybook_node_title').val(node.title || '');
    $('#storybook_node_description').val(node.description || '');
    renderNodeCharacters(node);
    renderConnections(node);
    $('#storybook_node_editor').show();

    if (node.generated_content) {
        $('#storybook_generated_text').text(node.generated_content);
        $('#storybook_generated_content').show();
    } else {
        $('#storybook_generated_content').hide();
    }
}

function renderNodeCharacters(node) {
    const container = $('#storybook_node_char_list');
    container.empty();
    if (!Array.isArray(node.characters)) return;

    for (const char of node.characters) {
        const charData = findCharacterByName(char.name);
        const avatar = charData?.avatar_url || 'img/ai4.png';
        const tag = $(`
            <div class="storybook_character_tag" data-char-name="${escapeHtml(char.name)}">
                <img src="${escapeHtml(avatar)}" alt="${escapeHtml(char.name)}">
                <span>${escapeHtml(char.name)}</span>
                <i class="fa-solid fa-times remove_char"></i>
            </div>
        `);
        tag.find('.remove_char').on('click', () => {
            removeCharacterFromNode(char.name);
        });
        container.append(tag);
    }
}

function renderConnections(node) {
    const container = $('#storybook_connections_list');
    container.empty();
    if (!Array.isArray(node.connections)) return;

    for (const conn of node.connections) {
        const item = $(`
            <div class="storybook_connection_item" data-conn-id="${conn.id || ''}">
                <span class="conn_from">${escapeHtml(conn.from)}</span>
                <span class="conn_arrow">→</span>
                <input type="text" class="conn_label_input" value="${escapeHtml(conn.label || '')}" placeholder="Relation label">
                <input type="text" class="conn_description_input" value="${escapeHtml(conn.description || '')}" placeholder="How do they interact?">
                <span class="conn_to">${escapeHtml(conn.to)}</span>
                <i class="fa-solid fa-times remove_conn"></i>
            </div>
        `);

        item.find('.conn_label_input').on('input', function () {
            conn.label = $(this).val();
            scheduleNodeSave();
        });
        item.find('.conn_description_input').on('input', function () {
            conn.description = $(this).val();
            scheduleNodeSave();
        });
        item.find('.remove_conn').on('click', function () {
            item.remove();
            const idx = node.connections.indexOf(conn);
            if (idx >= 0) node.connections.splice(idx, 1);
            scheduleNodeSave();
        });

        container.append(item);
    }
}

function addNewNode() {
    if (!currentStorybook) return;
    const node = {
        id: uuidv4(),
        title: 'New Node',
        position: (currentStorybook.nodes || []).length,
        description: '',
        characters: [],
        connections: [],
        generated_content: '',
    };
    if (!currentStorybook.nodes) currentStorybook.nodes = [];
    currentStorybook.nodes.push(node);
    selectedNodeId = node.id;
    saveStorybook();
    renderTimeline();
    selectNode(node.id);
}

async function deleteCurrentNode() {
    if (!selectedNodeId || !currentStorybookName) return;
    if (!confirm('Delete this story node?')) return;

    try {
        await fetch(`${STORYBOOK_DIR}/node/delete`, {
            method: 'POST',
            headers: getRequestHeaders(),
            body: JSON.stringify({ storybookName: currentStorybookName, nodeId: selectedNodeId }),
        });
        currentStorybook.nodes = (currentStorybook.nodes || []).filter(n => n.id !== selectedNodeId);
        selectedNodeId = null;
        renderTimeline();
        $('#storybook_node_editor').hide();
        saveStorybook();
    } catch (err) {
        console.error('Failed to delete node:', err);
    }
}

function getCurrentNode() {
    return currentStorybook?.nodes?.find(n => n.id === selectedNodeId);
}

function saveCurrentNode() {
    const node = getCurrentNode();
    if (!node) return;
    node.title = $('#storybook_node_title').val() || '';
    node.description = $('#storybook_node_description').val() || '';
    saveStorybook();
    renderTimeline();
    toastr.success('Node saved');
}

let nodeSaveTimeout;
function scheduleNodeSave() {
    clearTimeout(nodeSaveTimeout);
    nodeSaveTimeout = setTimeout(saveCurrentNode, 2000);
}

function debounceNodeAutoSave() {
    const node = getCurrentNode();
    if (!node) return;
    node.title = $('#storybook_node_title').val() || '';
    node.description = $('#storybook_node_description').val() || '';
    scheduleNodeSave();
}

async function saveStorybook() {
    if (!currentStorybookName || !currentStorybook) return;
    try {
        await fetch(`${STORYBOOK_DIR}/save`, {
            method: 'POST',
            headers: getRequestHeaders(),
            body: JSON.stringify({ name: currentStorybookName, data: currentStorybook }),
        });
    } catch (err) {
        console.error('Failed to save storybook:', err);
    }
}

function addCharacterToNode(charInfo) {
    const node = getCurrentNode();
    if (!node) return;
    if (!Array.isArray(node.characters)) node.characters = [];

    if (node.characters.find(c => c.name === charInfo.name)) return;

    node.characters.push({
        name: charInfo.name,
        chid: charInfo.chid || '',
    });
    renderNodeCharacters(node);
    scheduleNodeSave();
}

function removeCharacterFromNode(charName) {
    const node = getCurrentNode();
    if (!node) return;
    if (!Array.isArray(node.characters)) return;
    node.characters = node.characters.filter(c => c.name !== charName);
    renderNodeCharacters(node);
    scheduleNodeSave();
}

function findCharacterByName(name) {
    if (!Array.isArray(characters)) return null;
    const char = characters.find(c => c?.data?.name === name);
    if (char) {
        return {
            chid: char.avatar,
            name: char.data.name,
            avatar_url: char.avatar ? `/api/avatars/${encodeURIComponent(char.avatar)}` : null,
            data: char.data,
        };
    }
    return null;
}

function addConnection() {
    const node = getCurrentNode();
    if (!node) return;
    if (!Array.isArray(node.characters) || node.characters.length < 2) {
        toastr.warning('Need at least 2 characters to create a connection');
        return;
    }
    if (!Array.isArray(node.connections)) node.connections = [];

    const from = node.characters[0].name;
    const to = node.characters[node.characters.length > 1 ? 1 : 0].name;

    const conn = {
        id: uuidv4(),
        from: from,
        to: to,
        label: '',
        description: '',
    };
    node.connections.push(conn);
    renderConnections(node);
}

function showCharacterPicker() {
    const node = getCurrentNode();
    if (!node) return;

    const charNames = [];
    if (Array.isArray(characters)) {
        for (const char of characters) {
            if (char?.data?.name) {
                charNames.push({ chid: char.avatar, name: char.data.name });
            }
        }
    }

    if (charNames.length === 0) {
        toastr.warning('No characters available');
        return;
    }

    let html = '<div style="max-height:300px;overflow-y:auto;">';
    for (const char of charNames) {
        const alreadyAdded = node.characters?.find(c => c.name === char.name);
        html += `<div class="storybook_char_pick_item" style="padding:6px 8px;cursor:pointer;border-bottom:1px solid #444;" data-name="${escapeHtml(char.name)}" data-chid="${escapeHtml(char.chid)}">${escapeHtml(char.name)} ${alreadyAdded ? '✓' : ''}</div>`;
    }
    html += '</div>';

    const popup = $(html);
    popup.on('click', '.storybook_char_pick_item', function () {
        const name = $(this).data('name');
        const chid = $(this).data('chid');
        addCharacterToNode({ name: name, chid: chid });
        popup.remove();
    });

    const offset = $('#storybook_node_characters').offset();
    popup.css({
        position: 'absolute',
        top: offset.top + $('#storybook_node_characters').height(),
        left: offset.left,
        'z-index': 10000,
        background: 'var(--bg-primary, #1e1e1e)',
        border: '1px solid var(--border-color, #555)',
        'border-radius': '8px',
        'min-width': '200px',
        'max-width': '300px',
    });

    $('body').append(popup);
    $(document).one('click', function (e) {
        if (!$(e.target).closest(popup).length && !$(e.target).closest('#storybook_node_characters').length) {
            popup.remove();
        }
    });
    popup.on('click', function (e) {
        e.stopPropagation();
    });
}

async function generateNodeContent() {
    const node = getCurrentNode();
    if (!node || !currentStorybookName) {
        toastr.warning('No node selected');
        return;
    }
    if (!Array.isArray(node.characters) || node.characters.length === 0) {
        toastr.warning('Add at least one character to the node');
        return;
    }

    const prompt = buildGeneratePrompt(node);
    if (!prompt) {
        toastr.error('Failed to build generation prompt');
        return;
    }

    if (main_api !== 'openai') {
        toastr.error('Story generation requires Chat Completion API. Please switch to Chat Completion in API settings.');
        return;
    }

    toastr.info('Generating story content...');

    try {
        const model = getChatCompletionModel();

        if (!model) {
            toastr.error('No model selected. Please connect to an API and select a model first.');
            return;
        }

        const messages = [
            { role: 'system', content: '你是一个专业的小说作家。请用流畅生动的中文叙事，写出完整的故事情节。包括场景描写、人物动作、对话和心理活动。至少写8段。' },
            { role: 'user', content: prompt },
        ];

        const requestBody = {
            messages: messages,
            model: model,
            temperature: Number(oai_settings.temp_openai),
            frequency_penalty: Number(oai_settings.freq_pen_openai),
            presence_penalty: Number(oai_settings.pres_pen_openai),
            top_p: Number(oai_settings.top_p_openai),
            max_tokens: 8192,
            stream: false,
            chat_completion_source: oai_settings.chat_completion_source,
            include_reasoning: false,
            enable_web_search: false,
            request_images: false,
        };

        if (oai_settings.reverse_proxy) {
            requestBody.reverse_proxy = oai_settings.reverse_proxy;
            requestBody.proxy_password = oai_settings.proxy_password;
        }

        const response = await fetch('/api/backends/chat-completions/generate', {
            method: 'POST',
            headers: getRequestHeaders(),
            body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
            const text = await response.text();
            throw new Error(text || 'Generation failed');
        }

        const data = await response.json();

        let content = '';
        if (data?.choices?.[0]?.message?.content) {
            content = data.choices[0].message.content;
        } else if (data?.text) {
            content = data.text;
        } else if (data?.response) {
            content = data.response;
        } else if (typeof data === 'string') {
            content = data;
        } else {
            content = JSON.stringify(data);
        }

        if (!content || content.trim().length < 100) {
            throw new Error('Generated content is too short (' + (content?.length || 0) + ' chars). Try regenerating.');
        }

        node.generated_content = content;
        $('#storybook_generated_text').text(content);
        $('#storybook_generated_content').show();
        saveStorybook();
        toastr.success('Content generated (' + content.length + ' chars)');
    } catch (err) {
        console.error('Generation failed:', err);
        toastr.error('Failed to generate: ' + err.message);
    }
}

function buildGeneratePrompt(node) {
    const title = node.title || 'Untitled Chapter';
    const description = node.description || '';
    const characters = node.characters || [];
    const connections = node.connections || [];
    const storybookName = currentStorybook?.name || 'Story';

    let characterDescriptions = '';
    for (const char of characters) {
        const charData = findCharacterByName(char.name);
        let desc = '';
        if (charData?.data) {
            desc = `**${char.name}**: ${charData.data.description || ''}`;
            if (charData.data.personality) {
                desc += `\nPersonality: ${charData.data.personality}`;
            }
            if (charData.data.scenario) {
                desc += `\nScenario: ${charData.data.scenario}`;
            }
        }
        if (!desc) desc = `**${char.name}**`;
        characterDescriptions += desc + '\n\n';
    }

    let connectionsText = '';
    if (connections.length > 0) {
        connectionsText = 'Character relationships in this scene:\n';
        for (const conn of connections) {
            connectionsText += `- ${conn.from} → ${conn.to}: ${conn.label || 'interaction'}${conn.description ? ' - ' + conn.description : ''}\n`;
        }
    }

    return `You are writing the story "${storybookName}", chapter/scene: "${title}".

Scene description: ${description || 'Develop this scene naturally.'}

Characters:
${characterDescriptions}
${connectionsText}

Write a vivid, engaging narrative for this scene. Describe the setting, the characters' actions, their dialogue, and the emotional dynamics. Write at least 3-5 paragraphs of prose.`;
}

$(document).ready(() => {
    initStorybook();
});
