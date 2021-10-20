import * as vscode from 'vscode';
import { getNonce } from './utils'
const path = require('path')


function getWebviewOptions(extensionUri: vscode.Uri): vscode.WebviewOptions {
	return {
		// Enable javascript in the webview
		enableScripts: true,

		// And restrict the webview to only loading content from our extension's `media` directory.
		localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
	};
}

/**
 * Manages start sandbox webview panels
 */
export class SandboxStartPanel {
	/**
	 * Track the currently panel. Only allow a single panel to exist at a time.
	 */
	public static currentPanel: SandboxStartPanel | undefined;

	public static readonly viewType = 'startSandbox';

	private readonly _panel: vscode.WebviewPanel;
	private readonly _extensionUri: vscode.Uri;

    private _bpname: string;
    private _inputs: Array<string>;
    private _artifacts: object;
	private _disposables: vscode.Disposable[] = [];
	private readonly _branch: string;

	public static createOrShow(extensionUri: vscode.Uri, bpname:string, inputs:Array<string>, artifacts: object, branch: string) {
		const column = vscode.window.activeTextEditor
			? vscode.window.activeTextEditor.viewColumn
			: undefined;

		// If we already have a panel, show it.
		if (SandboxStartPanel.currentPanel) {
			SandboxStartPanel.currentPanel.updatePanel(bpname, inputs, artifacts);
            SandboxStartPanel.currentPanel._panel.reveal(column);
            return;
		}

		// Otherwise, create a new panel.
		const panel = vscode.window.createWebviewPanel(
			SandboxStartPanel.viewType,
			'Start Sandbox',
			column || vscode.ViewColumn.One,
			getWebviewOptions(extensionUri),
		);
		SandboxStartPanel.currentPanel = new SandboxStartPanel(panel, extensionUri, bpname, inputs, artifacts, branch);
	}

	private async startSandbox(bpname: string, sandbox_name: string, duration: number, inputs:object, artifacts:object, branch:string) {
		let inputsString = this._compose_comma_separated_string(inputs);
		let artifactsString = this._compose_comma_separated_string(artifacts);

		await vscode.commands.executeCommand('start_torque_sandbox', bpname, sandbox_name, duration, inputsString, artifactsString, branch)
		.then(async (result:Array<string>) => {
			vscode.commands.executeCommand('sandboxesExplorerView.refreshEntry')
			this._panel.dispose();
		})
	}

	private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, bpname:string, inputs:Array<string>, artifacts: object, branch: string) {
		this._panel = panel;
		this._extensionUri = extensionUri;
        this._bpname = decodeURI(bpname);
        this._inputs = inputs;
        this._artifacts = artifacts;
		this._branch = branch;

		// Set the webview's initial html content
		this._update();

		// Listen for when the panel is disposed
		// This happens when the user closes the panel or when the panel is closed programmatically
		this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

		// Handle messages from the webview
		this._panel.webview.onDidReceiveMessage(
			message => {
				switch (message.command) {
					case 'alert':
						vscode.window.showErrorMessage(message.text);
						return;
                    case 'run-command':
                        if (message.name == 'start-sandbox') {
                            this.startSandbox(this._bpname, message.sandbox_name, message.duration, message.inputs, message.artifacts, this._branch);
                        }
                        return;
				}
			},
			null,
			this._disposables
		);
	}

    public updatePanel(bpname:string, inputs:Array<string>, artifacts: object) {
        this._bpname = decodeURI(bpname);
        // this._space = space;
        this._inputs = inputs;
        this._artifacts = artifacts;

		// Set the webview's initial html content
		this._update();
    }

	public dispose() {
		SandboxStartPanel.currentPanel = undefined;

		// Clean up our resources
		this._panel.dispose();

		while (this._disposables.length) {
			const x = this._disposables.pop();
			if (x) {
				x.dispose();
			}
		}
	}
	private _compose_comma_separated_string(mapContainer: object) : string{
		let resultString = "";
		for (const [key, value] of Object.entries(mapContainer))
			resultString += `${key}=${value}, `

		resultString.trimEnd;
		if (resultString.length > 2) 
			resultString = resultString.substring(0, resultString.length - 2)
		
		return resultString
	}

	private _update() {
		const webview = this._panel.webview;

		this._panel.title = 'Start Sandbox';
		this._panel.webview.html = this._getHtmlForWebview(webview);
	}

    private _isEmpty(obj) {
        for (let j in obj) { return false }
        return true;
    }

	private _getHtmlForWebview(webview: vscode.Webview) {
		const stylesPathMainPath = vscode.Uri.joinPath(this._extensionUri, 'media', 'vscode.css');

		const stylesMainUri = webview.asWebviewUri(stylesPathMainPath);

		let cleanName = this._bpname;
		if (cleanName.endsWith('.yaml'))
			cleanName = cleanName.replace('.yaml', '').split(path.sep).slice(-1)[0]	
		if (cleanName.startsWith('[Sample]'))
			cleanName = cleanName.replace('[Sample]','');
		
		let generalHtml = "<table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        generalHtml += "<tr><td width='180px'>" + "Name" + "</td><td>" + "<input type='text' id='sandbox_name' value='" + cleanName + "'></td></tr>";
        generalHtml += "<tr><td width='180px'>" + "Duration (minutes) *" + "</td><td>" + "<input type='number' id='duration' value='30' min='10' max='3600'></td></tr>";
        generalHtml += "</table>";
		let inputsHtml = "";
		let postMessageProperties = "sandbox_name: document.getElementById('sandbox_name').value, duration: document.getElementById('duration').value"
        if (this._inputs.length > 0) {
            inputsHtml = "<b>Inputs</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
            postMessageProperties += ", inputs: {";        
            for (let i=0; i<this._inputs.length; i++)
            {
                inputsHtml += "<tr><td width='180px'>" + this._inputs[i]['name'] + (!this._inputs[i]['optional']? ' *': '') + "</td><td>" + "<input type=" + (this._inputs[i]['display_style']=='masked'?'password':'text') + " id='" + this._inputs[i]['name'] + "' value='" + (this._inputs[i]['default_value'] ? this._inputs[i]['default_value'] : '') + "'></td></tr>";
                postMessageProperties += `"${this._inputs[i]['name']}": document.getElementById('${this._inputs[i]['name']}').value,`;
            }
            inputsHtml += "</table>";
            postMessageProperties += "}";            
        }
        else
            postMessageProperties += ", inputs: {}";   

		let artifactsHtml = "";
        if (!this._isEmpty(this._artifacts)) {
            artifactsHtml = "<b>Artifacts</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
            postMessageProperties += ", artifacts: {";
            for (const [key, value] of Object.entries(this._artifacts)) {
                artifactsHtml += "<tr><td width='180px'>" + key + ' *' + "</td><td>" + "<input type='text' id='art_" + key + "' value='" + (value ? value : '') + "'></td></tr>";
                postMessageProperties += `"${key}": document.getElementById('art_${key}').value,`;
            }
            artifactsHtml += "</table>";
            postMessageProperties += "}";
            if (this._inputs.length > 0)
                artifactsHtml = "<br/>" + artifactsHtml;
        }
        else
            postMessageProperties += ", artifacts: {}";

        
        let startHtml = "<br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        startHtml += "<tr><td width='180px'><input type='button' id='start-btn' value='Start'></td><td></td></tr>";
        startHtml += "</table>";
        
		// Use a nonce to only allow specific scripts to be run
		const nonce = getNonce();
		
		let html = `<!DOCTYPE html>
			<html lang="en">
			<head>
				<meta charset="UTF-8">

				<!--
					Use a content security policy to only allow loading images from https or from our extension directory,
					and only allow scripts that have a specific nonce.
				-->
				<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; img-src ${webview.cspSource} https:; script-src 'nonce-${nonce}';">

				<meta name="viewport" content="width=device-width, initial-scale=1.0">

				<link href="${stylesMainUri}" rel="stylesheet">

				<title>Launch a New Sandbox</title>
			</head>
			<body>
                <br/>
				<h2>Launch a New Sandbox</h2>
				<h3>Blueprint: ${cleanName}</h3>
                <br/>
				${generalHtml}
                <br/>
				${inputsHtml}
                ${artifactsHtml}
                ${startHtml}
			</body>
            <script nonce="${nonce}">
                const vscode = acquireVsCodeApi();
                document.getElementById("start-btn").addEventListener("click", function() {
                    startSandbox();
                });
                function startSandbox() {                
                    vscode.postMessage({
                        command: 'run-command',
                        name: 'start-sandbox',
                        ${postMessageProperties}                    
                    });
                }
            </script>
			</html>`;
        return html;
	}
}