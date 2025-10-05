export namespace main {
	
	export class DependencyInfo {
	    installed: boolean;
	    version?: string;
	    status: string;
	
	    static createFrom(source: any = {}) {
	        return new DependencyInfo(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.installed = source["installed"];
	        this.version = source["version"];
	        this.status = source["status"];
	    }
	}
	export class CheckDependenciesResult {
	    success: boolean;
	    dependencies: Record<string, DependencyInfo>;
	    error?: string;
	
	    static createFrom(source: any = {}) {
	        return new CheckDependenciesResult(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.success = source["success"];
	        this.dependencies = this.convertValues(source["dependencies"], DependencyInfo, true);
	        this.error = source["error"];
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}
	
	export class MO2Installation {
	    path: string;
	    exe: string;
	    prefix: string;
	    version: string;
	
	    static createFrom(source: any = {}) {
	        return new MO2Installation(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.path = source["path"];
	        this.exe = source["exe"];
	        this.prefix = source["prefix"];
	        this.version = source["version"];
	    }
	}
	export class FindMO2Result {
	    success: boolean;
	    count: number;
	    installations: MO2Installation[];
	    error?: string;
	
	    static createFrom(source: any = {}) {
	        return new FindMO2Result(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.success = source["success"];
	        this.count = source["count"];
	        this.installations = this.convertValues(source["installations"], MO2Installation);
	        this.error = source["error"];
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}
	export class Game {
	    name: string;
	    path: string;
	    platform: string;
	    app_id: string;
	
	    static createFrom(source: any = {}) {
	        return new Game(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.name = source["name"];
	        this.path = source["path"];
	        this.platform = source["platform"];
	        this.app_id = source["app_id"];
	    }
	}
	
	export class ScanGamesResult {
	    success: boolean;
	    count: number;
	    games: Game[];
	    error?: string;
	
	    static createFrom(source: any = {}) {
	        return new ScanGamesResult(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.success = source["success"];
	        this.count = source["count"];
	        this.games = this.convertValues(source["games"], Game);
	        this.error = source["error"];
	    }
	
		convertValues(a: any, classs: any, asMap: boolean = false): any {
		    if (!a) {
		        return a;
		    }
		    if (a.slice && a.map) {
		        return (a as any[]).map(elem => this.convertValues(elem, classs));
		    } else if ("object" === typeof a) {
		        if (asMap) {
		            for (const key of Object.keys(a)) {
		                a[key] = new classs(a[key]);
		            }
		            return a;
		        }
		        return new classs(a);
		    }
		    return a;
		}
	}

}

