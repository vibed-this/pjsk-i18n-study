// IL2CPP Unity API helpers (AssetBundle / Type) — load after runtime.js
'use strict';

const _il2 = { ready: false };

function bindIl2CppExport(name, ret, args) {
    _il2[name] = new NativeFunction(findExport(name), ret, args);
}

function bindIl2CppUnity() {
    if (_il2.ready) return;
    bindIl2CppExport('il2cpp_domain_get', 'pointer', []);
    bindIl2CppExport('il2cpp_domain_get_assemblies', 'pointer', ['pointer', 'pointer']);
    bindIl2CppExport('il2cpp_assembly_get_image', 'pointer', ['pointer']);
    bindIl2CppExport('il2cpp_class_from_name', 'pointer', ['pointer', 'pointer', 'pointer']);
    bindIl2CppExport('il2cpp_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']);
    bindIl2CppExport('il2cpp_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']);
    bindIl2CppExport('il2cpp_class_get_type', 'pointer', ['pointer']);
    bindIl2CppExport('il2cpp_type_get_object', 'pointer', ['pointer']);
    _il2.ready = true;
}

function foreachAssemblyImage(visitor) {
    const domain = _il2.domain_get();
    const sizeBuf = Memory.alloc(Process.pointerSize);
    sizeBuf.writeUInt(0);
    const assemblies = _il2.domain_get_assemblies(domain, sizeBuf);
    const count = Process.pointerSize === 8 ? Number(sizeBuf.readU64()) : sizeBuf.readU32();
    for (let i = 0; i < count; i++) {
        const asm = assemblies.add(i * Process.pointerSize).readPointer();
        if (!asm || asm.isNull()) continue;
        const image = _il2.assembly_get_image(asm);
        if (!image || image.isNull()) continue;
        visitor(image);
    }
}

function resolveClass(namespace, className) {
    const ns = Memory.allocUtf8String(namespace);
    const name = Memory.allocUtf8String(className);
    let found = null;
    foreachAssemblyImage(function (image) {
        if (found) return;
        const klass = _il2.class_from_name(image, ns, name);
        if (klass && !klass.isNull()) found = klass;
    });
    return found;
}

function resolveMethod(klass, methodName, paramCount) {
    const name = Memory.allocUtf8String(methodName);
    return _il2.class_get_method_from_name(klass, name, paramCount);
}

function invokeMethod(method, thisObj, params) {
    const exc = Memory.alloc(Process.pointerSize);
    exc.writePointer(ptr(0));
    const argc = params ? params.length : 0;
    const argv = Memory.alloc(Process.pointerSize * Math.max(argc, 1));
    for (let i = 0; i < argc; i++) {
        argv.add(i * Process.pointerSize).writePointer(params[i]);
    }
    return _il2.runtime_invoke(method, thisObj || ptr(0), argv, exc);
}

function classToTypeObject(klass) {
    const type = _il2.class_get_type(klass);
    if (!type || type.isNull()) return null;
    return _il2.type_get_object(type);
}

function unityLoadAssetBundleFromFile(path) {
    const klass = resolveClass('UnityEngine', 'AssetBundle');
    if (!klass) throw new Error('UnityEngine.AssetBundle class not found');
    const method = resolveMethod(klass, 'LoadFromFile', 1);
    if (!method || method.isNull()) throw new Error('AssetBundle.LoadFromFile not found');
    const pathStr = makeStr(path);
    if (!pathStr) throw new Error('failed to alloc path string');
    const bundle = invokeMethod(method, null, [pathStr]);
    if (!bundle || bundle.isNull()) throw new Error('LoadFromFile returned null: ' + path);
    return bundle;
}

function unityLoadTmpFontAsset(bundle, assetName) {
    const bundleKlass = resolveClass('UnityEngine', 'AssetBundle');
    const tmpKlass = resolveClass('TMPro', 'TMP_FontAsset');
    if (!tmpKlass) throw new Error('TMPro.TMP_FontAsset class not found');
    const typeObj = classToTypeObject(tmpKlass);
    if (!typeObj || typeObj.isNull()) throw new Error('TMP_FontAsset type object missing');
    const method = resolveMethod(bundleKlass, 'LoadAsset', 2);
    if (!method || method.isNull()) throw new Error('AssetBundle.LoadAsset(name,type) not found');
    const nameStr = makeStr(assetName);
    const asset = invokeMethod(method, bundle, [nameStr, typeObj]);
    if (!asset || asset.isNull()) throw new Error('LoadAsset returned null: ' + assetName);
    return asset;
}