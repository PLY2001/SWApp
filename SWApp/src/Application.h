#pragma once
#include <unordered_map>
#include <map>
//#include <string>
//#include <atlstr.h>
//#include <memory>
//#include <mutex>
#include <regex>//正则表达式
#include "glm/glm.hpp"
#include "glm/gtc/matrix_transform.hpp"
#include "glm/gtc/type_ptr.hpp"
// #include <thread>
// #include <mutex>
// #include <atomic>
// #include <omp.h>

#include <io.h> //获取目录文件名

//获取略缩图
#include <shobjidl_core.h>
#include <thumbcache.h>
#include <atlstr.h>

#include <Commdlg.h>//浏览文件

//SolidWorks
#include <atlbase.h> //com
#import "sldworks.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids  // SOLIDWORKS type library
#import "swconst.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids   // SOLIDWORKS constants type library
#import "swdimxpert.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids  //SOLIDWORKS dimxpert library

namespace MyApp {

	struct MyAnnotation { //若有俩面之间的尺寸公差标注，那么这俩面都具有一样的MyAnnotation，但是定义在不同的MyFaceFeature中
		std::string Name;//标注名称
		swDimXpertAnnotationType_e Type = swDimXpertAnnotationType_unknown;//标注类型
		double AccuracySize = 0;//公差或粗糙度精度(毫米)
		int AccuracyLevel = 0;//公差或粗糙度等级
		
		//标注基准
		int IsDatum = 0;//是否是标注基准
		std::string DatumName;//基准名称

		//表面粗糙度
		int IsSFSymbol = 0;//是否是表面粗糙度
		swSFSymType_e SFSType = swSFBasic;//表面粗糙度类型

		//形位公差
		int IsGeoTolerance = 0;//是否是形位公差
		std::vector<std::string> ToleranceDatumNames;//公差基准
		int hasMCM = 0;//形位公差是否有实体状态
		swDimXpertMaterialConditionModifier_e MCMType = swDimXpertMaterialConditionModifier_unknown;//实体状态类型，即形位公差标注中的M和L

		//尺寸公差
		int IsDimTolerance = 0;//是否是尺寸公差
		double DimSize = 0;//尺寸大小
	};//标注 

	struct MyFaceFeature {
		std::string Name;//特征名称
		//CComBSTR AppliedFaceNameBSTR;//所属面名称
		double FaceArea = 0;//面的面积(mm)
		int AnnotationCount = 0;//标注数量
		std::vector<MyAnnotation> AnnotationArray;//标注数组
	};//特征面

	enum class MyState {
		Nothing, Succeed, Failed
	};//程序当前操作状态
	enum class SWState {
		Connected, FileOpen, PropertyGot, MBDGot, ModelLoaded, MassPropertyGot
	};//SW交互状态

	class MyApplication {
	private:
		std::map<std::string, std::string> property;//记录自定义属性
		std::map<std::string, std::string> summary;//记录摘要

		std::string MyStateMessage[3] = { "Unfinished","Succeed!","Failed!" };//提示文本		
		std::map<SWState, MyState> SWStateMap = {
			 {SWState::Connected,   MyState::Nothing}
			,{SWState::FileOpen,    MyState::Nothing}
			,{SWState::PropertyGot, MyState::Nothing}
			,{SWState::MBDGot,      MyState::Nothing}
			,{SWState::ModelLoaded, MyState::Nothing}
			,{SWState::MassPropertyGot, MyState::Nothing}
		};//记录SW交互状态
		MyState myState = MyState::Nothing;//记录程序当前操作状态

		bool toLoadProjectAddress = false;//是否弹出项目地址窗口
		bool toLoadPathSetting = false;//是否弹出工作目录设置窗口
		
		long DimXpertAnnotationCount = 0;//MBD标注数
		long DimXpertFeatureCount = 0;//MBD特征数

		std::unordered_map<std::string, MyFaceFeature> FaceMap;//记录MBD信息[面 : 特征(标注1，标注2...)]
		
		std::unordered_map<swDimXpertAnnotationType_e, int> GeoTolMap = {
			 {swDimXpertGeoTol_Angularity              ,8}//倾斜度M
			,{swDimXpertGeoTol_Circularity			   ,1}//圆度
			,{swDimXpertGeoTol_CircularRunout		   ,2}//圆跳动度
			,{swDimXpertGeoTol_CompositeLineProfile	   ,0}//复合 线轮廓度？
			,{swDimXpertGeoTol_CompositePosition	   ,0}//复合 位置度M？
			,{swDimXpertGeoTol_CompositeSurfaceProfile ,0}//复合 面轮廓度？
			,{swDimXpertGeoTol_Concentricity		   ,9}//同心度、同轴度M
			,{swDimXpertGeoTol_Cylindricity			   ,3}//圆柱度
			,{swDimXpertGeoTol_Flatness				   ,4}//平面度
			,{swDimXpertGeoTol_LineProfile			   ,5}//线轮廓度
			,{swDimXpertGeoTol_Parallelism			   ,10}//平行度M
			,{swDimXpertGeoTol_Perpendicularity		   ,11}//垂直度M
			,{swDimXpertGeoTol_Position				   ,12}//位置度M
			,{swDimXpertGeoTol_Straightness			   ,13}//直线度M
			,{swDimXpertGeoTol_SurfaceProfile		   ,6}//面轮廓度
			,{swDimXpertGeoTol_Symmetry				   ,14}//对称度M
			,{swDimXpertGeoTol_Tangency				   ,0}//切线度？
			,{swDimXpertGeoTol_TotalRunout			   ,7}//全跳动
		};//MBD标注类型集合：形位公差
		std::unordered_map<swDimXpertAnnotationType_e, int> DimTolMap = {
			 {swDimXpertDimTol_AngleBetween            ,1}//面间夹角公差
			,{swDimXpertDimTol_ChamferDimension		   ,2}//倒角公差
			,{swDimXpertDimTol_CompositeDistanceBetween,0}//面间混合距离公差？
			,{swDimXpertDimTol_ConeAngle			   ,3}//圆锥角公差
			,{swDimXpertDimTol_CounterBore			   ,4}//反向钻孔公差
			,{swDimXpertDimTol_CounterSinkAngle		   ,5}//反向沉头角度公差
			,{swDimXpertDimTol_CounterSinkDiameter	   ,6}//反向沉头直径公差
			,{swDimXpertDimTol_Depth				   ,7}//深度公差
			,{swDimXpertDimTol_Diameter				   ,8}//直径公差
			,{swDimXpertDimTol_DistanceBetween		   ,9}//面间距离公差
			,{swDimXpertDimTol_Length				   ,10}//长度公差
			,{swDimXpertDimTol_PatternAngleBetween	   ,11}//图案间角度公差
			,{swDimXpertDimTol_Radius				   ,12}//半径公差
			,{swDimXpertDimTol_Width				   ,13}//宽度公差
		};//MBD标注类型集合：尺寸公差
		std::unordered_map<swSFSymType_e, int> SFSMap = {
			 {swSFBasic         ,1}//基本
			,{swSFMachining_Req	,2}//要求切削加工
			,{swSFDont_Machine  ,3}//禁止切削加工
		};//MBD标注类型集合：表面粗糙度
		std::unordered_map<swDimXpertMaterialConditionModifier_e, int> MCMMap = {
			 {swDimXpertMCM_LMC  ,1}
			,{swDimXpertMCM_MMC	 ,2}
			,{swDimXpertMCM_RFS  ,3}
		};//MBD标注类型集合：实体状态类型
		//std::unordered_map<std::string, int> FitTolMap;
		std::unordered_map<std::string, int> FitTolMap = {
			{"a9", 1}, { "a10", 2 }, { "a11", 3 }, { "a12", 4 }, { "a13", 5 },
			{"b8",  6 },{"b9",  7}	,{"b10", 8}	,{"b11", 9}	,{"b12", 10},{"b13", 11},
			{"c8",  12},{"c9",  13},{"c10", 14},{"c11", 15},{"c12", 16},{"cd5", 17},{"cd6", 18},{"cd7", 19},{"cd8", 20},{"cd9", 21},{"cd10",22},
			{"d5",  23},{"d6",  24},{"d7",  25},{"d8",  26},{"d9",  27},{"d10", 28},{"d11", 29},{"d12", 30},{"d13", 31},
			{"e5",  32},{"e6",  33},{"e7",  34},{"e8",  35},{"e9",  36},{"e10", 37},{"ef3", 38},{"ef4", 39},{"ef5", 40},{"ef6", 41},{"ef7", 42},{"ef8", 43},{"ef9", 44},{"ef10",45},
			{"f3",  46},{"f4",  47},{"f5",  48},{"f6",  49},{"f7",  50},{"f8",  51},{"f9",  52},{"f10", 53},{"fg3", 54},{"fg4", 55},{"fg5", 56},{"fg6", 57},{"fg7", 58},{"fg8", 59},{"fg9", 60},{"fg10",61},
			{"g3",  62},{"g4",  63},{"g5",  64},{"g6",  65},{"g7",  66},{"g8",  67},{"g9",  68},{"g10", 69},
			{"h1",  70},{"h2",  71},{"h3",  72},{"h4",  73},{"h5",  74},{"h6",  75},{"h7",  76},{"h8",  77},{"h9",  78},{"h10", 79},{"h11", 80},{"h12", 81},{"h13", 82},{"h14", 83},{"h15", 84},{"h16", 85},{"h17", 86},{"h18", 87},
			{"js1", 88},{"js2", 89},{"js3", 90},{"js4", 91},{"js5", 92},{"js6", 93},{"js7", 94},{"js8", 95},{"js9", 96},{"js10",97},{"js11",98},{"js12",99},{"js13",100},{"js14",101},{"js15",102},{"js16",103},{"js17",104},{"js18",105},{"j5",  106},{"j6",  107},{"j7",  108},{"j8",  109},
			{"k3",  110},{"k4",  111},{"k5",  112},{"k6",  113},{"k7",  114},{"k8",  115},{"k9",  116},{"k10", 117},{"k11", 118},{"k12", 119},{"k13", 120},
			{"m3",  121},{"m4",  122},{"m5",  123},{"m6",  124},{"m7",  125},{"m8",  126},{"m9",  127},
			{"n3",  128},{"n4",  129},{"n5",  130},{"n6",  131},{"n7",  132},{"n8",  133},{"n9",  134},
			{"p3",  135},{"p4",  136},{"p5",  137},{"p6",  138},{"p7",  139},{"p8",  140},{"p9",  141},{"p10", 142},
			{"r3",  143},{"r4",  144},{"r5",  145},{"r6",  146},{"r7",  147},{"r8",  148},{"r9",  149},{"r10", 150},
			{"s3",  151},{"s4",  152},{"s5",  153},{"s6",  154},{"s7",  155},{"s8",  156},{"s9",  157},{"s10", 158},
			{"t5",  159},{"t6",  160},{"t7",  161},{"t8",  162},
			{"u5",  163},{"u6",  164},{"u7",  165},{"u8",  166},{"u9",  167},
			{"v5",  168},{"v6",  169},{"v7",  170},{"v8",  171},
			{"x5",  172},{"x6",  173},{"x7",  174},{"x8",  175},{"x9",  176},{"x10", 177},
			{"y6",  178},{"y7",  179},{"y8",  180},{"y9",  181},{"y10", 182},
			{"z6",  183},{"z7",  184},{"z8",  185},{"z9",  186},{"z10", 187},{"z11", 188},{"z6",  189},{"za7", 190},{"za8", 191},{"za9", 192},{"za10",193},{"za11",194},{"zb7", 195},{"zb8", 196},{"zb9", 197},{"zb10",198},{"zb11",199},{"zc7", 200},{"zc8", 201},{"zc9", 202},{"zc10",203},{"zc11",204},
			{"A9", 1}, { "A10", 2 }, { "A11", 3 }, { "A12", 4 }, { "A13", 5 },
			{ "B8",  6 },{"B9",  7}	,{"B10", 8}	,{"B11", 9}	,{"B12", 10},{"B13", 11},
			{"C8",  12},{"C9",  13},{"C10", 14},{"C11", 15},{"C12", 16},{"CD5", 17},{"CD6", 18},{"CD7", 19},{"CD8", 20},{"CD9", 21},{"CD10",22},
			{"D5",  23},{"D6",  24},{"D7",  25},{"D8",  26},{"D9",  27},{"D10", 28},{"D11", 29},{"D12", 30},{"D13", 31},
			{"E5",  32},{"E6",  33},{"E7",  34},{"E8",  35},{"E9",  36},{"E10", 37},{"EF3", 38},{"EF4", 39},{"EF5", 40},{"EF6", 41},{"EF7", 42},{"EF8", 43},{"EF9", 44},{"EF10",45},
			{"F3",  46},{"F4",  47},{"F5",  48},{"F6",  49},{"F7",  50},{"F8",  51},{"F9",  52},{"F10", 53},{"FG3", 54},{"FG4", 55},{"FG5", 56},{"FG6", 57},{"FG7", 58},{"FG8", 59},{"FG9", 60},{"FG10",61},
			{"G3",  62},{"G4",  63},{"G5",  64},{"G6",  65},{"G7",  66},{"G8",  67},{"G9",  68},{"G10", 69},
			{"H1",  70},{"H2",  71},{"H3",  72},{"H4",  73},{"H5",  74},{"H6",  75},{"H7",  76},{"H8",  77},{"H9",  78},{"H10", 79},{"H11", 80},{"H12", 81},{"H13", 82},{"H14", 83},{"H15", 84},{"H16", 85},{"H17", 86},{"H18", 87},
			{"JS1", 88},{"JS2", 89},{"JS3", 90},{"JS4", 91},{"JS5", 92},{"JS6", 93},{"JS7", 94},{"JS8", 95},{"JS9", 96},{"JS10",97},{"JS11",98},{"JS12",99},{"JS13",100},{"JS14",101},{"JS15",102},{"JS16",103},{"JS17",104},{"JS18",105},{"J5",  106},{"J6",  107},{"J7",  108},{"J8",  109},
			{"K3",  110},{"K4",  111},{"K5",  112},{"K6",  113},{"K7",  114},{"K8",  115},{"K9",  116},{"K10", 117},{"K11", 118},{"K12", 119},{"K13", 120},
			{"M3",  121},{"M4",  122},{"M5",  123},{"M6",  124},{"M7",  125},{"M8",  126},{"M9",  127},
			{"N3",  128},{"N4",  129},{"N5",  130},{"N6",  131},{"N7",  132},{"N8",  133},{"N9",  134},
			{"P3",  135},{"P4",  136},{"P5",  137},{"P6",  138},{"P7",  139},{"P8",  140},{"P9",  141},{"P10", 142},
			{"R3",  143},{"R4",  144},{"R5",  145},{"R6",  146},{"R7",  147},{"R8",  148},{"R9",  149},{"R10", 150},
			{"S3",  151},{"S4",  152},{"S5",  153},{"S6",  154},{"S7",  155},{"S8",  156},{"S9",  157},{"S10", 158},
			{"T5",  159},{"T6",  160},{"T7",  161},{"T8",  162},
			{"U5",  163},{"U6",  164},{"U7",  165},{"U8",  166},{"U9",  167},
			{"V5",  168},{"V6",  169},{"V7",  170},{"V8",  171},
			{"X5",  172},{"X6",  173},{"X7",  174},{"X8",  175},{"X9",  176},{"X10", 177},
			{"Y6",  178},{"Y7",  179},{"Y8",  180},{"Y9",  181},{"Y10", 182},
			{"Z6",  183},{"Z7",  184},{"Z8",  185},{"Z9",  186},{"Z10", 187},{"Z11", 188},{"Z6",  189},{"ZA7", 190},{"ZA8", 191},{"ZA9", 192},{"ZA10",193},{"ZA11",194},{"ZB7", 195},{"ZB8", 196},{"ZB9", 197},{"ZB10",198},{"ZB11",199},{"ZC7", 200},{"ZC8", 201},{"ZC9", 202},{"ZC10",203},{"ZC11",204},

		};//MBD标注类型集合：尺寸公差

		//char InputName[64] = "pipe";//用户输入名
		std::string CADName = "pole";//默认CAD文件名
		std::string CADType = ".SLDPRT";//默认CAD文件类型
		std::string CADPath = "C:\\Users\\PLY\\Desktop\\Files\\Projects\\SWApp\\SolidWorks Part\\";//默认CAD文件路径
		std::string CADTempPath = "C:\\Users\\PLY\\Desktop\\Files\\Projects\\SWApp\\SolidWorks Temp\\";//默认CAD临时文件路径

		glm::vec3 MassCenter = glm::vec3(0);//重心坐标
		glm::vec3 MinBoxVertex = glm::vec3(0);//包围盒
		glm::vec3 MaxBoxVertex = glm::vec3(0);//包围盒

		std::vector<std::string> TotalCADNames;//当前目录下所以CAD文件名
		bool toAutomatization = false;//是否自动化

		int fileIndex = 0;//当前CAD文件索引

		//bool toShowMBD = true;//是否渲染视图考虑MBD语义

		bool toShowThumbnail = false;//是否显示略缩图

		std::string PictureExportPathForMBD = "C:\\Users\\PLY\\Desktop\\Files\\Projects\\Pycharm Projects\\MBDViewFeature\\MBDViewDataset\\photos\\";
		std::string PictureExportPathFornoMBD = "C:\\Users\\PLY\\Desktop\\Files\\Projects\\Pycharm Projects\\MBDViewFeature\\MBDViewDataset_noMBD\\photos\\";
		std::string ModelPictureExportPath = "C:\\Users\\PLY\\Desktop\\Files\\Projects\\Pycharm Projects\\MBDViewFeature\\MBDViewModelPicture\\";
		
		std::string PythonHome = "C:/Users/PLY/anaconda3/envs/torchgpu";
		std::string PythonProjectPath = "C:/Users/PLY/Desktop/Files/Projects/Pycharm Projects/MBDViewFeature";

		void EnableDocking();//开启Docking特性
		void ShowMenuBar();//显示菜单栏
		void ShowImguiExample();//显示Imgui示例
		bool ShowMessage(const char* message);//显示ImGui弹窗，而ImGui::OpenPopup("提示")用于弹出弹窗
		bool ShowPathSetting();//显示ImGui弹窗，而ImGui::OpenPopup("工作路径设置")用于弹出弹窗
		bool ConnectSW();//连接SW
		bool OpenFile();//打开文件
		bool ReadProperty();//读取文件属性
		bool ReadMassProperty();//获取质量属性
		bool ReadMBD();//读取MBD特征及其标注
		bool ReadNoMBDFace();
		bool LoadModel();//加载模型

		std::string GbkToUtf8(const char* src_str);//将SW默认文本的GBK编码转为ImGui显示文本用的Utf8编码
		bool ReadSafeArray(VARIANT* vt, VARENUM vtType, int dimensional, LPVOID* pData, LONG* itemCount);//读取SAFEARRAY数组(输入VARIANT变量，数组元素类型，数组维度，输出数组，输出数组大小)
		template<typename T>
		bool CreatVARIANTArray(int size, VARENUM type, T* buffer, VARIANT* array);//创建含SAFEARRAY的VARIANT变量(数组大小，数组元素类型，输入数组，输出VARIANT变量)
		double ReadDoubleFromString(std::string textstr);//读取字符串中的小数，如6.3
		wchar_t* multi_Byte_To_Wide_Char(const std::string& pKey);
		std::string string_To_UTF8(const std::string& str);
		void SetLinearDimAccuarcyLevel(int* level, double size, float f, float m, float c, float v);
		void SetSFSAccuarcyLevel(int* level, double size);
		void SetGeoAccuarcyLevel(int* level, double size, double faceArea, swDimXpertAnnotationType_e annoType);
		void SetGeoRealAccuarcyLevel(int* level, double size, float a, float b, float c, float d, float e, float f);
		
		void ReadAnnotationData(swDimXpertAnnotationType_e annoType,double* toleranceSize, int* toleranceLevel,std::string* myDatumName, std::vector<std::string>& datumNames,swDimXpertMaterialConditionModifier_e* MCMType, double* dimSize, double faceArea);//读取标注数据
		void DatumData(std::string* myDatumName);//读取基准信息
		void GeoTolData(swDimXpertAnnotationType_e annoType, double* toleranceSize, int* toleranceLevel, std::vector<std::string>& datumNames, swDimXpertMaterialConditionModifier_e* MCMType, double faceArea);//读取形位公差数据
		void DimTolData(swDimXpertAnnotationType_e annoType, double* toleranceSize, int* toleranceLevel, double* dimSize);//读取尺寸公差数据

		void GetFiles(std::string path, std::vector<std::string>& files);//读取当前目录下所有CAD文件名
		std::string GetFilesFromExplorer();
		bool CopyFileToCADPath();
	
	public:
		void ShowMyApp();
		inline std::unordered_map<std::string, MyFaceFeature>& GetFaceMap() { return FaceMap; };//获取面哈希表的引用
		inline std::map<SWState, MyState>& GetSWStateMap() { return SWStateMap; };//获取SW交互状态的引用
		inline std::string GetExportPathUtf8() { return CADTempPath + GetCADNameUtf8() + "\\"; };//获取保存模型时的路径
		inline std::string GetExportPath() { return CADTempPath + CADName + "\\"; };//获取保存模型时的路径
		inline std::string GetPictureExportPath(bool isMBDView) { return isMBDView? PictureExportPathForMBD : PictureExportPathFornoMBD; };//获取保存模型时的路径
		inline std::string GetModelPictureExportPath() { return ModelPictureExportPath; };//获取保存模型时的路径
		inline std::string GetCADName() { return CADName; };//获取保存模型时的名称
		inline std::string GetCADNameUtf8() { return string_To_UTF8(CADName); };//获取保存模型时的名称
		inline std::string GetCADPath() { return CADPath; };//获取保存模型时的路径
		inline std::string GetCADTempPath() { return CADTempPath; };//获取保存模型时的路径
		inline std::string GetPythonHome() { return PythonHome; };//获取python库的路径
		inline std::string GetPythonProjectPath() { return PythonProjectPath; };//获取python项目的路径
		inline glm::vec3 GetMassCenter() { return MassCenter; };//获取质心(毫米)
		inline glm::vec3 GetMinBoxVertex() { return MinBoxVertex; };//获取包围盒
		inline glm::vec3 GetMaxBoxVertex() { return MaxBoxVertex; };//获取包围盒

		inline bool ShouldAutomatization() { return toAutomatization; }//确定要自动化
		inline void StopAutomatization() { toAutomatization = false; }//停止自动化
		//inline bool ShouldShowMBD() { return toShowMBD; }//确定要考虑MBD语义
		inline bool ShouldLoadThumbnail() { return toShowThumbnail; }//确定要加载略缩图
		inline void StopLoadThumbnail() { toShowThumbnail = false; }//停止加载略缩图
		inline void SetCADPath(std::string path) { CADPath = path; };//获取保存模型时的路径
		inline void SetCADTempPath(std::string path) { CADTempPath = path; };//获取保存模型时的路径
		inline void SetPictureExportPathForMBD(std::string path) {PictureExportPathForMBD = path;}
		inline void SetPictureExportPathFornoMBD(std::string path) { PictureExportPathFornoMBD = path; }
		inline void SetModelPictureExportPath(std::string path) { ModelPictureExportPath = path; }
		inline void SetPythonHome(std::string path) { PythonHome = path; }
		inline void SetPythonProjectPath(std::string path) { PythonProjectPath = path; }

		
		std::string GetNextToOpenFileName();//获取打开模型时的路径
		HBITMAP GetThumbnailEx();
		BOOL SaveBitmapToFile(HBITMAP hBitmap, const CString& szfilename);
		bool ClearFiles(std::string clearPath);

		bool StartOpenFile(std::string inputName);//打开文件
		bool StartReadProperty();//读取文件属性
		bool StartReadMassProperty();//获取质量属性
		bool StartReadMBD();//读取MBD特征及其标注
		bool StartLoadModel();//加载模型

		void StartOpenFileFromButton(std::string inputName);//由按钮打开文件

		long allTime = 0;//MBD读取总耗时
		long feTime = 0;//特征读取循环耗时（包含标注、面耗时）
		long aTime = 0;//标注读取循环耗时
		long fTime = 0;//面读取循环耗时
		long swaTime = 0;//表面粗糙度读取循环耗时
		long bTime = 0;//非MBD面读取循环耗时

		//模型初始姿态
		float angleList[3] = { 0,0,0 };

		//std::mutex mtx;
		//void FeatureLoop(int feIndex, IDispatch** & myfeData);
		//void AnnotationLoop(int aIndex, IDispatch**& myaData, MyFaceFeature &faceFeature);

	//极致简洁的单例模式，运用了static的性质
	private:
		static std::shared_ptr<MyApplication> instance;
		
		MyApplication() {};
		~MyApplication() {};
	public:
		static MyApplication& GetInstance() {
			static MyApplication instance;
			return instance;
		}
		

	};

	//class MyApplicationAdapter
	//{
	//private:
	//	MyApplication* t;
	//public:
	//	MyApplicationAdapter(MyApplication* t_) :t(t_) {}
	//	void operator()(int feIndex, IDispatch**& myfeData, MyFaceFeature& faceFeature) { t->AnnotationLoop(feIndex, myfeData, faceFeature); };
	//};


    
}
