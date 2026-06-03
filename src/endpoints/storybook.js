import fs from 'node:fs';
import path from 'node:path';

import express from 'express';
import sanitize from 'sanitize-filename';
import { sync as writeFileAtomicSync } from 'write-file-atomic';
import { uuidv4 } from '../util.js';

export const router = express.Router();

router.post('/list', async (request, response) => {
    try {
        const dirs = request.user.directories;
        const storybookDir = dirs.storybooks;
        if (!fs.existsSync(storybookDir)) {
            fs.mkdirSync(storybookDir, { recursive: true });
        }
        const jsonFiles = (await fs.promises.readdir(storybookDir, { withFileTypes: true }))
            .filter((file) => file.isFile() && path.extname(file.name).toLowerCase() === '.json')
            .sort((a, b) => a.name.localeCompare(b.name));

        const data = [];
        for (const file of jsonFiles) {
            try {
                const filePath = path.join(storybookDir, file.name);
                const fileContents = await fs.promises.readFile(filePath, 'utf8');
                const parsed = JSON.parse(fileContents);
                const fileNameWithoutExt = path.parse(file.name).name;
                data.push({
                    file_id: fileNameWithoutExt,
                    name: parsed?.name || fileNameWithoutExt,
                    node_count: Array.isArray(parsed?.nodes) ? parsed.nodes.length : 0,
                    created_at: parsed?.createdAt || null,
                    updated_at: parsed?.updatedAt || null,
                });
            } catch (err) {
                console.warn(`Error reading storybook file ${file.name}:`, err);
            }
        }
        return response.send(data);
    } catch (err) {
        console.error('Error reading storybook directory:', err);
        return response.sendStatus(500);
    }
});

router.post('/get', (request, response) => {
    if (!request.body?.name) {
        return response.sendStatus(400);
    }

    const dirs = request.user.directories;
    const storybookDir = dirs.storybooks;
    const filename = sanitize(`${request.body.name}.json`);
    const filePath = path.join(storybookDir, filename);

    if (!fs.existsSync(filePath)) {
        return response.status(404).send('Storybook not found');
    }

    const contents = fs.readFileSync(filePath, 'utf8');
    return response.send(JSON.parse(contents));
});

router.post('/save', (request, response) => {
    if (!request.body?.name || !request.body?.data) {
        return response.sendStatus(400);
    }

    const dirs = request.user.directories;
    const storybookDir = dirs.storybooks;
    if (!fs.existsSync(storybookDir)) {
        fs.mkdirSync(storybookDir, { recursive: true });
    }

    const filename = sanitize(`${request.body.name}.json`);
    const filePath = path.join(storybookDir, filename);

    const data = {
        ...request.body.data,
        updatedAt: new Date().toISOString(),
    };
    if (!data.createdAt) {
        data.createdAt = new Date().toISOString();
    }

    writeFileAtomicSync(filePath, JSON.stringify(data, null, 4));
    return response.send({ ok: true, name: request.body.name });
});

router.post('/delete', (request, response) => {
    if (!request.body?.name) {
        return response.sendStatus(400);
    }

    const dirs = request.user.directories;
    const storybookDir = dirs.storybooks;
    const filename = sanitize(`${request.body.name}.json`);
    const filePath = path.join(storybookDir, filename);

    if (!fs.existsSync(filePath)) {
        return response.status(404).send('Storybook not found');
    }

    fs.unlinkSync(filePath);
    return response.sendStatus(200);
});

router.post('/rename', (request, response) => {
    if (!request.body?.oldName || !request.body?.newName) {
        return response.sendStatus(400);
    }

    const dirs = request.user.directories;
    const storybookDir = dirs.storybooks;
    const oldFilename = sanitize(`${request.body.oldName}.json`);
    const newFilename = sanitize(`${request.body.newName}.json`);
    const oldPath = path.join(storybookDir, oldFilename);
    const newPath = path.join(storybookDir, newFilename);

    if (!fs.existsSync(oldPath)) {
        return response.status(404).send('Storybook not found');
    }

    if (fs.existsSync(newPath)) {
        return response.status(409).send('A storybook with this name already exists');
    }

    const contents = fs.readFileSync(oldPath, 'utf8');
    const data = JSON.parse(contents);
    data.name = request.body.newName;
    data.updatedAt = new Date().toISOString();

    writeFileAtomicSync(newPath, JSON.stringify(data, null, 4));
    fs.unlinkSync(oldPath);
    return response.send({ ok: true, name: request.body.newName });
});

router.post('/node/save', (request, response) => {
    if (!request.body?.storybookName) {
        return response.sendStatus(400);
    }

    const dirs = request.user.directories;
    const storybookDir = dirs.storybooks;
    const filename = sanitize(`${request.body.storybookName}.json`);
    const filePath = path.join(storybookDir, filename);

    if (!fs.existsSync(filePath)) {
        return response.status(404).send('Storybook not found');
    }

    const contents = fs.readFileSync(filePath, 'utf8');
    const storybook = JSON.parse(contents);

    if (!Array.isArray(storybook.nodes)) {
        storybook.nodes = [];
    }

    const nodeData = request.body.node;
    if (!nodeData.id) {
        nodeData.id = uuidv4();
    }

    const existingIndex = storybook.nodes.findIndex(n => n.id === nodeData.id);
    if (existingIndex >= 0) {
        storybook.nodes[existingIndex] = nodeData;
    } else {
        storybook.nodes.push(nodeData);
    }

    storybook.updatedAt = new Date().toISOString();
    writeFileAtomicSync(filePath, JSON.stringify(storybook, null, 4));
    return response.send({ ok: true, node: nodeData });
});

router.post('/node/delete', (request, response) => {
    if (!request.body?.storybookName || !request.body?.nodeId) {
        return response.sendStatus(400);
    }

    const dirs = request.user.directories;
    const storybookDir = dirs.storybooks;
    const filename = sanitize(`${request.body.storybookName}.json`);
    const filePath = path.join(storybookDir, filename);

    if (!fs.existsSync(filePath)) {
        return response.status(404).send('Storybook not found');
    }

    const contents = fs.readFileSync(filePath, 'utf8');
    const storybook = JSON.parse(contents);

    storybook.nodes = (storybook.nodes || []).filter(n => n.id !== request.body.nodeId);
    storybook.updatedAt = new Date().toISOString();
    writeFileAtomicSync(filePath, JSON.stringify(storybook, null, 4));
    return response.send({ ok: true });
});

router.post('/node/reorder', (request, response) => {
    if (!request.body?.storybookName || !request.body?.nodeIds) {
        return response.sendStatus(400);
    }

    const dirs = request.user.directories;
    const storybookDir = dirs.storybooks;
    const filename = sanitize(`${request.body.storybookName}.json`);
    const filePath = path.join(storybookDir, filename);

    if (!fs.existsSync(filePath)) {
        return response.status(404).send('Storybook not found');
    }

    const contents = fs.readFileSync(filePath, 'utf8');
    const storybook = JSON.parse(contents);

    const nodeMap = new Map(storybook.nodes.map(n => [n.id, n]));
    storybook.nodes = request.body.nodeIds.map((id, index) => {
        const node = nodeMap.get(id);
        if (node) {
            node.position = index;
        }
        return node;
    }).filter(Boolean);

    storybook.updatedAt = new Date().toISOString();
    writeFileAtomicSync(filePath, JSON.stringify(storybook, null, 4));
    return response.send({ ok: true });
});

router.post('/duplicate', (request, response) => {
    if (!request.body?.name) {
        return response.sendStatus(400);
    }

    const dirs = request.user.directories;
    const storybookDir = dirs.storybooks;
    const filename = sanitize(`${request.body.name}.json`);
    const filePath = path.join(storybookDir, filename);

    if (!fs.existsSync(filePath)) {
        return response.status(404).send('Storybook not found');
    }

    const contents = fs.readFileSync(filePath, 'utf8');
    const data = JSON.parse(contents);

    let newName = `${request.body.name} (Copy)`;
    let newFilename = sanitize(`${newName}.json`);
    let newPath = path.join(storybookDir, newFilename);

    let counter = 1;
    while (fs.existsSync(newPath)) {
        newName = `${request.body.name} (Copy ${counter})`;
        newFilename = sanitize(`${newName}.json`);
        newPath = path.join(storybookDir, newFilename);
        counter++;
    }

    data.name = newName;
    data.createdAt = new Date().toISOString();
    data.updatedAt = new Date().toISOString();

    writeFileAtomicSync(newPath, JSON.stringify(data, null, 4));
    return response.send({ ok: true, name: newName });
});
