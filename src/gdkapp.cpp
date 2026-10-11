// krkrz_gdk: Xbox (GXDK) 用 Application
//
// Desktop (Gaming.Desktop.x64) は core の sdl3/environ/stdapp.cpp をそのまま使う。
// Xbox は WIN32 が真になるため core が stdapp.cpp を自動で入れるが、フォルダ選択
// ダイアログやプラグイン DLL のロードなどデスクトップ前提の処理を含むので、
// KRKRZ_APP_PLATFORM_OVERRIDE で外してこちらを使う。
// パス正規化まわりは stdapp.cpp の Windows 版と同じ実装。

#include "tjsCommHead.h"
#include "CharacterSet.h"
#include "DebugIntf.h"
#include "LogIntf.h"
#include "StorageIntf.h"

#include "app.h"
#include "ExecutableOverlay.h"

#include <XPersistentLocalStorage.h>

#include <algorithm>
#include <filesystem>
#include <fstream>

namespace {

void CheckLastDelimiter(std::string &path)
{
	if (path.empty() || (path.back() != '/' && path.back() != '\\')) {
		path += '\\';
	}
}

bool IsExistent(const std::string &path)
{
	tjs_string w;
	TVPUtf8ToUtf16(w, path);
	return TVPIsExistentStorageNoSearch(w.c_str());
}

// 実行ファイル自身に xp3 が結合されているか (stdapp.cpp と同じ)
bool HasXP3InExecutable(const tjs_string &exePath)
{
	std::error_code ec;
	const std::filesystem::path path(exePath.c_str());
	const uint64_t size = std::filesystem::file_size(path, ec);
	if (ec || size < 64) return false;
	std::ifstream f(path, std::ios::binary);
	if (!f) return false;
	tTVPReadAtFunc reader = [&f](uint64_t pos, void *buf, size_t len) -> size_t {
		f.clear();
		f.seekg((std::streamoff)pos);
		f.read(static_cast<char *>(buf), (std::streamsize)len);
		return (size_t)f.gcount();
	};
	uint64_t offset = 0;
	return TVPFindXP3InExecutable(reader, size, offset);
}

tjs_string ModulePath()
{
	wchar_t buf[1024];
	const DWORD len = ::GetModuleFileNameW(NULL, buf, static_cast<DWORD>(std::size(buf)));
	if (len > 0 && len < std::size(buf)) return tjs_string(reinterpret_cast<const tjs_char *>(buf));
	return tjs_string();
}

} // namespace

bool SDL_NormalizeStorageName(tjs_string &name);

class GDKApplication : public SDL3Application {
public:
	GDKApplication() {}
	virtual ~GDKApplication() {}
	virtual bool InitPath() override;
	virtual const tjs_string &TempPath() const override;

protected:
	virtual const char *getPlatformTagSpec() const override;
};

bool GDKApplication::InitPath()
{
	std::string appPath = SDL_GetBasePath();
	CheckLastDelimiter(appPath);

	// 引数でプロジェクトパスを明示指定 (開発用)
	extern int GetSystemSecurityOption(const char *name);
	const bool acceptFileArgument = GetSystemSecurityOption("acceptfilenameargument") != 0;
	const tjs_string exePath = ModulePath();
	std::string projectPath;
	if (!acceptFileArgument && _nargs.size() > 1) {
		std::filesystem::path p(_nargs[1].c_str());
		auto u8 = p.u8string();
		std::string pathU8(reinterpret_cast<const char *>(u8.c_str()), u8.size());
		projectPath = p.is_relative() ? appPath + pathU8 : pathU8;
		CheckLastDelimiter(projectPath);
	} else if (IsExistent(appPath + "data.xp3")) {
		projectPath = appPath + "data.xp3>";
	} else if (!exePath.empty() && HasXP3InExecutable(exePath)) {
		TVPUtf16ToUtf8(projectPath, exePath);
		projectPath += ">";
	} else if (IsExistent(appPath + "data/startup.tjs")) {
		projectPath = appPath + "data/";
	} else {
		// コンソールにはプロジェクトフォルダを選ばせる手段が無い
		TVPLOG_ERROR("No project data (data.xp3 / data/startup.tjs) in {}", appPath);
		return false;
	}
	TVPLOG_INFO("appPath: {}", appPath);
	TVPLOG_INFO("projectPath: {}", projectPath);

	TVPUtf8ToUtf16(_AppPath, appPath);
	TVPUtf8ToUtf16(_ProjectPath, projectPath);
	_ExePath = exePath.empty() ? _AppPath + TJS_W("krkrz.exe") : exePath;
	// プラグインは全て static (DLL は読まない)
	_PluginPath = TJS_W("");

	// エンジンリソースは exe に埋め込まず layout/resource/ にファイルで置く
	// (KRKRZ_RESOURCE_EXTERNAL)
	tjs_string res;
	TVPUtf8ToUtf16(res, appPath + "resource/");
	std::replace(res.begin(), res.end(), TJS_W('\\'), TJS_W('/'));
	SDL_NormalizeStorageName(res);
	_ResourcePath = res;
	{
		std::string r;
		TVPUtf16ToUtf8(r, _ResourcePath);
		TVPLOG_INFO("resourcePath: {}", r);
	}
	return true;
}

// テンポラリ領域。パッケージのフォルダは読み取り専用なので、
// MicrosoftGame.config で PersistentLocalStorage を確保している場合はその下の tmp/ を使う。
const tjs_string &GDKApplication::TempPath() const
{
	static bool inited = false;
	static tjs_string tempPath;
	if (!inited) {
		inited = true;
		char buf[1024];
		size_t used = 0;
		std::string path;
		if (SUCCEEDED(XPersistentLocalStorageGetPath(sizeof(buf), buf, &used)) && used > 0) {
			path = buf;
			CheckLastDelimiter(path);
			path += "tmp\\";
			std::error_code ec;
			std::filesystem::create_directories(std::filesystem::u8path(path), ec);
		} else {
			auto u8 = std::filesystem::temp_directory_path().u8string();
			path.assign(reinterpret_cast<const char *>(u8.c_str()), u8.size());
			CheckLastDelimiter(path);
		}
		TVPUtf8ToUtf16(tempPath, path);
	}
	return tempPath;
}

// config_<tag>.cf / System.platformTag 用 (一般 → 具体)
const char *GDKApplication::getPlatformTagSpec() const
{
#if defined(KRKRZ_GDK_SCARLETT)
	return "xbox;scarlett";
#elif defined(KRKRZ_GDK_XBOXONE)
	return "xbox;xboxone";
#else
	return "xbox";
#endif
}

// 機種別グローバル初期化処理 (XGameRuntime の初期化は SDL 側が行う)
void TVPAppInit(int argc, char *argv[])
{
}

SDL3Application *GetSDL3Application()
{
	if (!Application) {
		new GDKApplication(); // ctor が Application = this を設定
	}
	return static_cast<SDL3Application *>(Application);
}

bool SDL_CommitSavedata()
{
	return true;
}

bool SDL_RollbackSavedata()
{
	return true;
}

bool SDL_NormalizeStorageName(tjs_string &name)
{
	const size_t namelen = name.length();
	if (namelen == 0) return false;

	// drive:path 形式
	if (namelen >= 2 &&
		((name[0] >= TJS_W('a') && name[0] <= TJS_W('z')) || (name[0] >= TJS_W('A') && name[0] <= TJS_W('Z'))) &&
		name[1] == TJS_W(':')) {
		tjs_string newname(TJS_W("file://./"));
		newname += name[0];
		newname += (name.c_str() + 2);
		name = newname;
		return true;
	}
	if (namelen >= 5 && name.substr(0, 5) == TJS_W("file:")) {
		return false;
	}
	if (namelen >= 2 && name[0] == TJS_W('\\') && name[1] == TJS_W('\\')) {
		name = TJS_W("file://./") + name;
		return true;
	}
	return false;
}

void SDL_GetLocallyAccessibleName(tjs_string &name)
{
	const tjs_char *ptr = name.c_str();
	tjs_string newname;

	if (TJS_strncmp(ptr, TJS_W("./"), 2)) {
		newname = tjs_string(TJS_W("\\\\")) + ptr;
	} else {
		ptr += 2; // skip "./"
		if (*ptr) {
			tjs_char dch = tolower(*ptr);
			if (dch >= TJS_W('a') && dch <= TJS_W('z')) {
				ptr++;
				if (*ptr == TJS_W('/')) {
					newname = dch;
					newname += TJS_W(":");
					newname += ptr;
				}
			}
		}
	}
	std::replace(newname.begin(), newname.end(), TJS_W('/'), TJS_W('\\'));
	name = newname;
}

bool SDL_GetListAt(const tjs_char *name, std::function<void(const tjs_char *, bool isDir)> lister, bool withDir)
{
	return false;
}

iTJSBinaryStream *SDL_OpenStream(const char *path, const tjs_uint32 flags)
{
	return nullptr;
}
